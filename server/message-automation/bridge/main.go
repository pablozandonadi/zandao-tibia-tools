// Private adapter: sends messages and collects only group commands ("!word ..."). Default mode is fake and never creates a WhatsApp client.
package main

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"database/sql"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"
	"time"

	qrcode "github.com/skip2/go-qrcode"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	"google.golang.org/protobuf/proto"
	_ "modernc.org/sqlite"
)

var internalID = regexp.MustCompile(`^[a-f0-9]{32}$`)
var errUnavailable = errors.New("unavailable")
var errUncertain = errors.New("dispatch uncertain")

type session struct {
	mu       sync.Mutex
	client   *whatsmeow.Client
	db       *sql.DB
	revoked  bool
	qr       string
	expires  int64
	cancel   context.CancelFunc
	attempts map[string]bool
	imu      sync.Mutex
	inbox    []inboxItem
	tmu      sync.Mutex
	targets  map[string]types.JID // group handle -> JID, refreshed at most every few minutes (typing and sending must be quick)
	targetAt time.Time
}

// inboxItem is the only thing ever kept from a group: a command line, with opaque handles for group and sender.
type inboxItem struct {
	ID     string `json:"id"`
	Group  string `json:"group"`
	Sender string `json:"sender"`
	Text   string `json:"text"`
	At     int64  `json:"at"`
}

const inboxMax = 100
const inboxTTL = 180 * time.Second
const commandMax = 200
type bridge struct {
	mu       sync.Mutex
	sessions map[string]*session
	dir      string
	token    string
	real     bool
}
type group struct {
	ID    string `json:"id"`
	Label string `json:"label"`
}

// An actual Linux dm-crypt/LUKS mount is required, not an environment assertion.
func encryptedMount(dir string) error {
	if runtime.GOOS != "linux" {
		return errUnavailable
	}
	absolute, err := filepath.EvalSymlinks(dir)
	if err != nil {
		return err
	}
	mounts, err := os.ReadFile("/proc/self/mountinfo")
	if err != nil {
		return err
	}
	source := ""
	best := 0
	for _, line := range strings.Split(string(mounts), "\n") {
		pair := strings.SplitN(line, " - ", 2)
		if len(pair) != 2 {
			continue
		}
		left := strings.Fields(pair[0])
		right := strings.Fields(pair[1])
		if len(left) < 5 || len(right) < 2 {
			continue
		}
		mount := strings.ReplaceAll(left[4], `\040`, " ")
		if (absolute == mount || strings.HasPrefix(absolute, mount+string(os.PathSeparator))) && len(mount) > best {
			source = right[1]
			best = len(mount)
		}
	}
	device, err := filepath.EvalSymlinks(source)
	if err != nil {
		return err
	}
	name := filepath.Base(device)
	if !strings.HasPrefix(name, "dm-") {
		return errUnavailable
	}
	uuid, err := os.ReadFile(filepath.Join("/sys/class/block", name, "dm/uuid"))
	if err != nil || !strings.HasPrefix(string(uuid), "CRYPT-LUKS") {
		return errUnavailable
	}
	return nil
}

func (b *bridge) load(id string) (*session, error) {
	if !internalID.MatchString(id) {
		return nil, errUnavailable
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if s := b.sessions[id]; s != nil {
		return s, nil
	}
	if len(b.sessions) >= 50 {
		return nil, errUnavailable
	}
	s := &session{attempts: map[string]bool{}}
	if b.real {
		if _, err := os.Stat(filepath.Join(b.dir, id+".revoked")); err == nil {
			return nil, errUnavailable
		}
		db, err := sql.Open("sqlite", "file:"+filepath.ToSlash(filepath.Join(b.dir, id+".sqlite"))+"?_pragma=foreign_keys(1)&_pragma=busy_timeout(5000)")
		if err != nil {
			return nil, err
		}
		db.SetMaxOpenConns(1)
		container := sqlstore.NewWithDB(db, "sqlite3", nil)
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err = container.Upgrade(ctx); err != nil {
			db.Close()
			return nil, err
		}
		device, err := container.GetFirstDevice(ctx)
		if err != nil {
			db.Close()
			return nil, err
		}
		if _, err = db.Exec("CREATE TABLE IF NOT EXISTS automation_attempts(id TEXT PRIMARY KEY,state TEXT NOT NULL)"); err != nil {
			db.Close()
			return nil, err
		}
		s.db = db
		s.client = whatsmeow.NewClient(device, nil)
		s.client.ManualHistorySyncDownload = true
		// The hist_sync receipt only acknowledges the notification (nothing is downloaded); without it the phone shows "chat sync paused".
		s.client.DisableManualHistorySyncReceipt = false
		s.client.AutomaticMessageRerequestFromPhone = false
		s.client.UseRetryMessageStore = false
		s.client.SetForceActiveDeliveryReceipts(false)
		// No read receipts, history download or message store. The only handler keeps group command lines ("!word ...") in memory.
		s.client.AddEventHandler(func(evt any) {
			if m, ok := evt.(*events.Message); ok {
				b.collect(id, s, m)
			}
		})
	}
	b.sessions[id] = s
	return s, nil
}

func (b *bridge) handle(id string, jid types.JID) string {
	mac := hmac.New(sha256.New, []byte(b.token))
	mac.Write([]byte(id + "\x00" + jid.String()))
	return hex.EncodeToString(mac.Sum(nil))
}
// commandText returns the text of a group message only when it is a short "!command" line; everything else is dropped at once.
func commandText(m *events.Message) string {
	if m == nil || m.Message == nil || m.Info.IsFromMe || !m.Info.IsGroup {
		return ""
	}
	text := m.Message.GetConversation()
	if text == "" {
		text = m.Message.GetExtendedTextMessage().GetText()
	}
	text = strings.TrimSpace(text)
	if len(text) < 2 || len(text) > commandMax || text[0] != '!' || strings.ContainsAny(text, "\r\n\x00") {
		return ""
	}
	return text
}

// collect keeps a bounded in-memory list of command lines. Nothing else from the group is stored or logged.
func (b *bridge) collect(id string, s *session, m *events.Message) {
	text := commandText(m)
	if text == "" {
		return
	}
	item := inboxItem{ID: string(m.Info.ID), Group: b.handle(id, m.Info.Chat), Sender: b.handle(id, m.Info.Sender), Text: text, At: m.Info.Timestamp.Unix()}
	s.imu.Lock()
	defer s.imu.Unlock()
	if len(s.inbox) >= inboxMax {
		s.inbox = s.inbox[1:]
	}
	s.inbox = append(s.inbox, item)
}

// typing shows "typing…" (or clears it) in an authorized group while the bot prepares a reply.
func (b *bridge) typing(ctx context.Context, id string, s *session, g, state string) error {
	if s.revoked || (state != "composing" && state != "paused") {
		return errUnavailable
	}
	if !b.real {
		if g != "fake-group" {
			return errUnavailable
		}
		return nil
	}
	jid, err := b.target(ctx, id, s, g)
	if err != nil {
		return err
	}
	presence := types.ChatPresenceComposing
	if state == "paused" {
		presence = types.ChatPresencePaused
	}
	return s.client.SendChatPresence(ctx, jid, presence, types.ChatPresenceMediaText)
}

// drain hands over the fresh command lines and forgets them.
func (s *session) drain(now time.Time) []inboxItem {
	s.imu.Lock()
	defer s.imu.Unlock()
	fresh := []inboxItem{}
	for _, item := range s.inbox {
		if now.Sub(time.Unix(item.At, 0)) <= inboxTTL {
			fresh = append(fresh, item)
		}
	}
	s.inbox = nil
	return fresh
}
// target resolves a group handle to its JID using the cached group list (refreshed every few minutes). Asking WhatsApp for the whole
// list on every send made sends fail whenever that query was slow; a known group keeps working from the cache in that case.
func (b *bridge) target(ctx context.Context, id string, s *session, g string) (types.JID, error) {
	return resolveTarget(s, g, func() (map[string]types.JID, error) {
		_, targets, err := b.groups(ctx, id, s)
		return targets, err
	})
}

func resolveTarget(s *session, g string, load func() (map[string]types.JID, error)) (types.JID, error) {
	s.tmu.Lock()
	jid, ok := s.targets[g]
	fresh := time.Since(s.targetAt) <= 5*time.Minute
	s.tmu.Unlock()
	if ok && fresh {
		return jid, nil
	}
	targets, err := load()
	if err != nil {
		if ok {
			return jid, nil
		}
		return types.JID{}, err
	}
	s.tmu.Lock()
	s.targets, s.targetAt = targets, time.Now()
	s.tmu.Unlock()
	if found, exists := targets[g]; exists {
		return found, nil
	}
	return types.JID{}, errUnavailable
}

func (b *bridge) groups(ctx context.Context, id string, s *session) ([]group, map[string]types.JID, error) {
	if s.revoked {
		return nil, nil, errUnavailable
	}
	if !b.real {
		return []group{{ID: "fake-group", Label: "Grupo sintético (simulação)"}}, map[string]types.JID{}, nil
	}
	if !s.client.IsLoggedIn() || !s.client.IsConnected() {
		return nil, nil, errUnavailable
	}
	joined, err := s.client.GetJoinedGroups(ctx)
	if err != nil {
		return nil, nil, err
	}
	groups := []group{}
	targets := map[string]types.JID{}
	for _, g := range joined {
		key := b.handle(id, g.JID)
		groups = append(groups, group{ID: key, Label: g.Name})
		targets[key] = g.JID
	}
	return groups, targets, nil
}
func (b *bridge) status(s *session) map[string]any {
	state := "connected"
	if s.revoked {
		state = "revoked"
	} else if b.real && (!s.client.IsLoggedIn() || !s.client.IsConnected()) {
		state = "disconnected"
	}
	result := map[string]any{"state": state, "simulated": !b.real}
	if s.qr != "" && s.expires > time.Now().Unix() && !s.revoked {
		result["qrImage"] = s.qr
		result["expiresAt"] = s.expires
		result["state"] = "pairing"
	} else {
		s.qr = ""
		s.expires = 0
	}
	return result
}
func (b *bridge) pair(id string, s *session) error {
	if s.revoked {
		return errUnavailable
	}
	if !b.real {
		return nil
	}
	if s.client.IsLoggedIn() && s.client.IsConnected() {
		return nil
	}
	if s.qr != "" && s.expires > time.Now().Unix() {
		return nil
	}
	if err := os.WriteFile(filepath.Join(b.dir, id+".accepted"), []byte("risk accepted\n"), 0600); err != nil {
		return err
	}
	if s.cancel != nil {
		s.cancel()
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	s.cancel = cancel
	// whatsmeow keeps the Connect context for handlers and auto-reconnect, so the
	// connection uses the client's background context; ctx only bounds the QR channel.
	if s.client.Store.ID != nil {
		return s.client.Connect()
	}
	codes, err := s.client.GetQRChannel(ctx)
	if err != nil {
		cancel()
		return err
	}
	go func() {
		for item := range codes {
			s.mu.Lock()
			if s.revoked {
				s.mu.Unlock()
				return
			}
			if item.Event == whatsmeow.QRChannelEventCode {
				png, e := qrcode.Encode(item.Code, qrcode.Medium, 300)
				if e == nil {
					s.qr = "data:image/png;base64," + base64.StdEncoding.EncodeToString(png)
					s.expires = time.Now().Add(item.Timeout).Unix()
				}
			} else {
				s.qr = ""
				s.expires = 0
			}
			s.mu.Unlock()
		}
	}()
	return s.client.Connect()
}
func (b *bridge) revoke(id string, s *session) error {
	s.revoked = true
	s.qr = ""
	s.expires = 0
	if s.cancel != nil {
		s.cancel()
	}
	if !b.real {
		return nil
	}
	s.client.EnableAutoReconnect = false
	// Persist tombstone before logout; never reconnect this session after a failure/restart.
	file, err := os.OpenFile(filepath.Join(b.dir, id+".revoked"), os.O_CREATE|os.O_WRONLY, 0600)
	if err != nil {
		s.client.Disconnect()
		return err
	}
	if err = file.Sync(); err != nil {
		file.Close()
		s.client.Disconnect()
		return err
	}
	file.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	err = s.client.Logout(ctx)
	s.client.Disconnect()
	return err
}
func (b *bridge) send(ctx context.Context, id string, s *session, g, text, attempt string) (map[string]any, error) {
	if s.revoked || !internalID.MatchString(attempt) || len(text) == 0 || len(text) > 64000 {
		return nil, errUnavailable
	}
	if !b.real {
		if g != "fake-group" || s.attempts[attempt] {
			return nil, errUnavailable
		}
		s.attempts[attempt] = true
		return map[string]any{"id": attempt, "simulated": true}, nil
	}
	jid, err := b.target(ctx, id, s, g)
	if err != nil {
		return nil, err
	}
	if _, err = s.db.ExecContext(ctx, "INSERT INTO automation_attempts(id,state) VALUES(?,'sending')", attempt); err != nil {
		return nil, errUnavailable
	}
	result, err := s.client.SendMessage(ctx, jid, &waE2E.Message{Conversation: proto.String(text)}, whatsmeow.SendRequestExtra{ID: types.MessageID(attempt), Timeout: 8 * time.Second, CheckPermissions: true})
	state := "accepted"
	if err != nil {
		state = "uncertain"
	}
	_, persistErr := s.db.ExecContext(context.Background(), "UPDATE automation_attempts SET state=? WHERE id=?", state, attempt)
	if err != nil || persistErr != nil {
		return nil, errUncertain
	}
	return map[string]any{"id": result.ID, "simulated": false}, nil
}

func (b *bridge) resume(ctx context.Context, id string, s *session) error {
	if s.revoked {
		return errUnavailable
	}
	if !b.real {
		return nil
	}
	if _, err := os.Stat(filepath.Join(b.dir, id+".accepted")); err != nil {
		return errUnavailable
	}
	if s.client.Store.ID == nil {
		return errUnavailable
	}
	if s.client.IsConnected() && s.client.IsLoggedIn() {
		return nil
	}
	// Request-scoped ctx would end the connection as soon as the HTTP reply is sent.
	return s.client.Connect()
}

func reply(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(value)
}
func decode(r *http.Request, out any) error {
	decoder := json.NewDecoder(io.LimitReader(r.Body, 65537))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(out); err != nil {
		return err
	}
	var extra any
	if decoder.Decode(&extra) != io.EOF {
		return errUnavailable
	}
	return nil
}
func (b *bridge) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	supplied := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
	if subtle.ConstantTimeCompare([]byte(supplied), []byte(b.token)) != 1 || len(b.token) < 32 {
		reply(w, 401, map[string]string{"error": "unauthorized"})
		return
	}
	if r.Header.Get("Origin") != "" || r.ContentLength > 65536 {
		reply(w, 403, map[string]string{"error": "forbidden"})
		return
	}
	parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	if len(parts) < 2 || len(parts) > 3 || parts[0] != "sessions" || !internalID.MatchString(parts[1]) {
		reply(w, 404, map[string]string{"error": "not found"})
		return
	}
	id := parts[1]
	s, err := b.load(id)
	if err != nil {
		reply(w, 409, map[string]string{"error": "unavailable"})
		return
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	ctx, cancel := context.WithTimeout(r.Context(), 12*time.Second)
	defer cancel()
	if len(parts) == 2 && r.Method == http.MethodGet {
		reply(w, 200, b.status(s))
		return
	}
	if len(parts) == 2 && r.Method == http.MethodDelete {
		err = b.revoke(id, s)
		if err == nil {
			reply(w, 200, map[string]string{"state": "revoked"})
			return
		}
	}
	if len(parts) == 3 {
		switch parts[2] {
		case "resume":
			if r.Method == http.MethodPost && b.resume(ctx, id, s) == nil {
				reply(w, 200, b.status(s))
				return
			}
		case "pair":
			if r.Method == http.MethodPost {
				var body struct {
					RiskAccepted bool `json:"riskAccepted"`
				}
				if decode(r, &body) == nil && body.RiskAccepted {
					err = b.pair(id, s)
					if err == nil {
						reply(w, 200, b.status(s))
						return
					}
				}
			}
		case "groups":
			if r.Method == http.MethodGet {
				var groups []group
				groups, _, err = b.groups(ctx, id, s)
				if err == nil {
					reply(w, 200, map[string]any{"groups": groups})
					return
				}
			}
		case "typing":
				if r.Method == http.MethodPost {
					var body struct {
						Group string `json:"group"`
						State string `json:"state"`
					}
					if decode(r, &body) == nil && b.typing(ctx, id, s, body.Group, body.State) == nil {
						reply(w, 200, map[string]any{"ok": true, "simulated": !b.real})
						return
					}
				}
			case "inbox":
				if r.Method == http.MethodPost && !s.revoked {
					reply(w, 200, map[string]any{"messages": s.drain(time.Now()), "simulated": !b.real})
					return
				}
			case "send":
			if r.Method == http.MethodPost {
				var body struct {
					Group   string `json:"group"`
					Text    string `json:"text"`
					Attempt string `json:"attempt"`
				}
				if decode(r, &body) == nil {
					var result map[string]any
					result, err = b.send(ctx, id, s, body.Group, body.Text, body.Attempt)
					if err == nil {
						reply(w, 200, result)
						return
					}
					log.Printf("send failed before dispatch=%t err=%v", !errors.Is(err, errUncertain), err) // never the text or the group
					if errors.Is(err, errUncertain) {
						reply(w, 502, map[string]string{"error": "unavailable", "dispatch": "uncertain"})
						return
					}
					reply(w, 409, map[string]string{"error": "unavailable", "dispatch": "not_started"})
					return
				}
			}
		}
	}
	reply(w, 409, map[string]string{"error": "unavailable"})
}
func main() {
	tokenPath := os.Getenv("BRIDGE_TOKEN_FILE")
	raw, err := os.ReadFile(tokenPath)
	if err != nil || len(strings.TrimSpace(string(raw))) < 32 {
		fmt.Fprintln(os.Stderr, "bridge configuration invalid")
		os.Exit(1)
	}
	b := &bridge{token: strings.TrimSpace(string(raw)), dir: os.Getenv("BRIDGE_STATE_DIR"), sessions: map[string]*session{}}
	mode := os.Getenv("BRIDGE_MODE")
	if mode != "" && mode != "fake" && mode != "real" {
		fmt.Fprintln(os.Stderr, "invalid bridge mode")
		os.Exit(1)
	}
	b.real = mode == "real"
	if b.real {
		if os.Getenv("BRIDGE_ENABLE_REAL") != "I_ACCEPT_UNOFFICIAL_WHATSAPP" || encryptedMount(b.dir) != nil {
			fmt.Fprintln(os.Stderr, "real mode requires authorized encrypted Linux mount")
			os.Exit(1)
		}
		// No startup scan/reconnect. Only an active backend dispatch can request resume.
	}
	server := &http.Server{Addr: "127.0.0.1:8788", Handler: b, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 20 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 8192}
	fmt.Println("bridge ready on loopback")
	if err = server.ListenAndServe(); err != nil {
		fmt.Fprintln(os.Stderr, "bridge stopped")
		os.Exit(1)
	}
}
