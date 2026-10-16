import struct
import unittest
from voice import audio_capture


class CaptureTests(unittest.TestCase):
    def test_preroll_internal_pause_and_tail(self):
        capture = audio_capture.Capture(1000)
        quiet = b'\0\0' * 100
        speech = struct.pack('<h', 2000) * 100
        for _ in range(10):
            self.assertIsNone(capture.feed(quiet))
        for _ in range(3):
            self.assertIsNone(capture.feed(speech))
        for _ in range(5):
            self.assertIsNone(capture.feed(quiet))
        self.assertIsNone(capture.feed(speech))
        for _ in range(7):
            self.assertIsNone(capture.feed(quiet))
        result = capture.feed(quiet)
        self.assertIsNotNone(result)
        self.assertEqual(result[:1000], quiet * 5)
        self.assertIn(speech * 3 + quiet * 5 + speech, result)
        self.assertEqual(result[-1600:], quiet * 8)

    def test_maximum_and_reset_do_not_replay_audio(self):
        capture = audio_capture.Capture(1000)
        speech = struct.pack('<h', 2000) * 100
        result = None
        for _ in range(150):
            result = capture.feed(speech)
        self.assertIsNone(result, 'Never execute truncated commands')
        self.assertTrue(capture.exceeded)
        capture.feed(speech)
        capture.reset()
        quiet = b'\0\0' * 100
        for _ in range(10):
            self.assertIsNone(capture.feed(quiet))


if __name__ == '__main__':
    unittest.main()
