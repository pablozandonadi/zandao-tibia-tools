package main

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
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
