package main

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	"google.golang.org/protobuf/proto"
)

const testID = "0123456789abcdef0123456789abcdef"
const attemptID = "abcdef0123456789abcdef0123456789"

func fixture() *bridge {
	return &bridge{token: strings.Repeat("a", 48), sessions: map[string]*session{}}
}
func call(b *bridge, method, path, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+b.token)
	recorder := httptest.NewRecorder()
	b.ServeHTTP(recorder, req)
	return recorder
}
func TestFakePairGroupsSendAndRevoke(t *testing.T) {
	b := fixture()
	base := "/sessions/" + testID
	if call(b, "POST", base+"/pair", `{"riskAccepted":false}`).Code != 409 {
		t.Fatal("risk acceptance required")
	}
	if call(b, "POST", base+"/pair", `{"riskAccepted":true}`).Code != 200 {
		t.Fatal("fake pairing failed")
	}
	if call(b, "GET", base+"/groups", "").Code != 200 {
		t.Fatal("groups failed")
	}
	wrong := `{"group":"arbitrary-jid","text":"private fixture","attempt":"` + attemptID + `"}`
	if call(b, "POST", base+"/send", wrong).Code != 409 {
		t.Fatal("arbitrary destination accepted")
	}
	body := `{"group":"fake-group","text":"private fixture","attempt":"` + attemptID + `"}`
	response := call(b, "POST", base+"/send", body)
	if response.Code != 200 || !strings.Contains(response.Body.String(), `"simulated":true`) {
		t.Fatal("fake send not distinguished")
	}
	if call(b, "POST", base+"/send", body).Code != 409 {
		t.Fatal("duplicate attempt repeated")
	}
	if call(b, "DELETE", base, "").Code != 200 {
		t.Fatal("revoke failed")
	}
	if call(b, "POST", base+"/pair", `{"riskAccepted":true}`).Code != 409 {
		t.Fatal("revoked session paired")
	}
	if call(b, "POST", base+"/send", body).Code != 409 {
		t.Fatal("revoked session sent")
	}
}
func TestAuthorizationAndPayload(t *testing.T) {
	b := fixture()
	req := httptest.NewRequest("GET", "/sessions/"+testID, nil)
	recorder := httptest.NewRecorder()
	b.ServeHTTP(recorder, req)
	if recorder.Code != 401 {
		t.Fatal("missing auth accepted")
	}
	if call(b, "GET", "/sessions/../../escape", "").Code != 404 {
		t.Fatal("path accepted")
	}
	if call(b, "POST", "/sessions/"+testID+"/pair", `{"riskAccepted":true,"owner":"victim"}`).Code != 409 {
		t.Fatal("unknown fields accepted")
	}
	if call(b, "POST", "/sessions/"+testID+"/pair", `{"riskAccepted":true} {}`).Code != 409 {
		t.Fatal("trailing JSON accepted")
	}
}
func TestQRExpiresAndRevocationClears(t *testing.T) {
	b := fixture()
	s, _ := b.load(testID)
	s.qr = "data:image/png;base64,c2VjcmV0"
	s.expires = time.Now().Add(time.Minute).Unix()
	response := call(b, "GET", "/sessions/"+testID, "")
	var value map[string]any
	json.Unmarshal(response.Body.Bytes(), &value)
	if value["qrImage"] == nil {
		t.Fatal("owner QR missing")
	}
	s.expires = time.Now().Add(-time.Second).Unix()
	response = call(b, "GET", "/sessions/"+testID, "")
	if strings.Contains(response.Body.String(), "qrImage") {
		t.Fatal("expired QR disclosed")
	}
	s.qr = "secret"
	call(b, "DELETE", "/sessions/"+testID, "")
	if s.qr != "" {
		t.Fatal("revoked QR retained")
	}
}
func TestPersistentSQLiteStoreWithoutConnecting(t *testing.T) {
	b := fixture()
	b.real = true
	b.dir = t.TempDir()
	s, err := b.load(testID)
	if err != nil {
		t.Fatal(err)
	}
	defer s.db.Close()
	if s.client.IsConnected() || s.client.IsLoggedIn() {
		t.Fatal("load connected unexpectedly")
	}
	if !s.client.ManualHistorySyncDownload || s.client.UseRetryMessageStore {
		t.Fatal("history/retry persistence enabled")
	}
	if s.client.DisableManualHistorySyncReceipt {
		t.Fatal("hist_sync receipt disabled: phone shows chat sync paused")
	}
	s.db.Close()
	b.sessions = map[string]*session{}
	if err = os.WriteFile(filepath.Join(b.dir, testID+".revoked"), []byte("revoked"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = b.load(testID); err == nil {
		t.Fatal("revocation tombstone ignored")
	}
}

func commandEvent(text string, group, fromMe bool, at time.Time) *events.Message {
	return &events.Message{
		Info: types.MessageInfo{
			MessageSource: types.MessageSource{Chat: types.NewJID("120363000000000001", types.GroupServer), Sender: types.NewJID("5511999990000", types.DefaultUserServer), IsGroup: group, IsFromMe: fromMe},
			ID:            "ABC123", Timestamp: at,
		},
		Message: &waE2E.Message{Conversation: proto.String(text)},
	}
}

func TestOnlyGroupCommandsAreCollected(t *testing.T) {
	b := fixture()
	s := &session{attempts: map[string]bool{}}
	now := time.Now()
	for _, text := range []string{"oi pessoal", "!", "   ", "!" + strings.Repeat("a", 200), "!help\nsegredo", "hello !help", "tem !help aqui"} {
		b.collect(testID, s, commandEvent(text, true, false, now))
	}
	b.collect(testID, s, commandEvent("!help", false, false, now)) // conversa privada
	b.collect(testID, s, commandEvent("!help", true, true, now))   // mensagem do próprio bot
	if got := s.drain(now); len(got) != 0 {
		t.Fatalf("collected non-commands: %v", got)
	}
	b.collect(testID, s, commandEvent("  !duelo A x B  ", true, false, now))
	extended := commandEvent("", true, false, now)
	extended.Message = &waE2E.Message{ExtendedTextMessage: &waE2E.ExtendedTextMessage{Text: proto.String("!evolucao Fulano")}}
	b.collect(testID, s, extended)
	got := s.drain(now)
	if len(got) != 2 || got[0].Text != "!duelo A x B" || got[1].Text != "!evolucao Fulano" {
		t.Fatalf("unexpected commands: %v", got)
	}
	if len(got[0].Group) != 64 || strings.Contains(got[0].Group+got[0].Sender, "120363") || strings.Contains(got[0].Sender, "5511") || got[0].Group == got[0].Sender {
		t.Fatal("handles must be opaque HMACs")
	}
	if len(s.drain(now)) != 0 {
		t.Fatal("drain must forget what it handed over")
	}
}

func TestInboxExpiresAndIsBounded(t *testing.T) {
	b := fixture()
	s := &session{attempts: map[string]bool{}}
	now := time.Now()
	b.collect(testID, s, commandEvent("!velho", true, false, now.Add(-10*time.Minute)))
	for i := 0; i < inboxMax+20; i++ {
		b.collect(testID, s, commandEvent("!help", true, false, now))
	}
	if len(s.inbox) != inboxMax {
		t.Fatalf("inbox not bounded: %d", len(s.inbox))
	}
	for _, item := range s.drain(now) {
		if item.Text != "!help" {
			t.Fatal("expired command delivered")
		}
	}
	b.collect(testID, s, commandEvent("!velho", true, false, now.Add(-10*time.Minute)))
	if len(s.drain(now)) != 0 {
		t.Fatal("expired command delivered")
	}
}

func TestInboxEndpointFakeMode(t *testing.T) {
	b := fixture()
	base := "/sessions/" + testID
	response := call(b, "POST", base+"/inbox", "")
	if response.Code != 200 || !strings.Contains(response.Body.String(), `"messages":[]`) || !strings.Contains(response.Body.String(), `"simulated":true`) {
		t.Fatalf("inbox: %d %s", response.Code, response.Body.String())
	}
	if call(b, "GET", base+"/inbox", "").Code != 409 {
		t.Fatal("inbox must be POST only")
	}
	call(b, "DELETE", base, "")
	if call(b, "POST", base+"/inbox", "").Code != 409 {
		t.Fatal("revoked session returned commands")
	}
}

func TestTypingFakeMode(t *testing.T) {
	b := fixture()
	base := "/sessions/" + testID
	ok := call(b, "POST", base+"/typing", `{"group":"fake-group","state":"composing"}`)
	if ok.Code != 200 || !strings.Contains(ok.Body.String(), `"simulated":true`) {
		t.Fatalf("typing: %d %s", ok.Code, ok.Body.String())
	}
	if call(b, "POST", base+"/typing", `{"group":"fake-group","state":"paused"}`).Code != 200 {
		t.Fatal("paused rejected")
	}
	for _, body := range []string{`{"group":"arbitrary-jid","state":"composing"}`, `{"group":"fake-group","state":"recording"}`, `{"group":"fake-group"}`, `{"group":"fake-group","state":"composing","extra":1}`} {
		if call(b, "POST", base+"/typing", body).Code != 409 {
			t.Fatalf("accepted: %s", body)
		}
	}
	if call(b, "GET", base+"/typing", "").Code != 409 {
		t.Fatal("typing must be POST only")
	}
	call(b, "DELETE", base, "")
	if call(b, "POST", base+"/typing", `{"group":"fake-group","state":"composing"}`).Code != 409 {
		t.Fatal("revoked session typed")
	}
}

func TestResolveTargetUsesCacheAndSurvivesSlowGroupList(t *testing.T) {
	s := &session{}
	jid := types.NewJID("111", types.GroupServer)
	calls := 0
	load := func() (map[string]types.JID, error) { calls++; return map[string]types.JID{"g1": jid}, nil }
	failing := func() (map[string]types.JID, error) { calls++; return nil, errUnavailable }

	if got, err := resolveTarget(s, "g1", load); err != nil || got != jid || calls != 1 {
		t.Fatalf("first lookup must load the list once: %v %v %d", got, err, calls)
	}
	if got, err := resolveTarget(s, "g1", failing); err != nil || got != jid || calls != 1 {
		t.Fatalf("fresh cache must not ask WhatsApp again: %v %v %d", got, err, calls)
	}
	s.targetAt = time.Now().Add(-10 * time.Minute)
	if got, err := resolveTarget(s, "g1", failing); err != nil || got != jid || calls != 2 {
		t.Fatalf("stale cache with a failing refresh must keep a known group working: %v %v %d", got, err, calls)
	}
	if _, err := resolveTarget(s, "unknown", failing); err == nil {
		t.Fatal("an unknown group with a failing list must be refused")
	}
	if _, err := resolveTarget(s, "unknown", load); err == nil {
		t.Fatal("a group missing from a fresh list must be refused")
	}
}
