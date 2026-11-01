import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from visionguide.api_server import app


class DeviceApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_health_and_tool_registry(self):
        self.assertEqual(self.client.get('/health').status_code, 200)
        payload = self.client.get('/api/v1/tools').json()
        names = {item['name'] for item in payload['tools']}
        self.assertIn('gmail_unread', names)
        self.assertIn('media_playback', names)
        self.assertIn('wifi_set', names)

    def test_wifi_change_is_gated_before_execution_and_token_binds_device(self):
        response = self.client.post('/api/v1/command', json={
            'text': 'Turn Wi-Fi off', 'device_id': 'mobile-a'
        })
        self.assertEqual(response.status_code, 200)
        result = response.json()['result']
        self.assertEqual(result['status'], 'confirmation_required')
        confirmation_id = result['confirmation_id']

        wrong_device = self.client.post('/api/v1/confirm', json={
            'confirmation_id': confirmation_id, 'device_id': 'mobile-b', 'confirmed': True
        })
        self.assertEqual(wrong_device.status_code, 403)

        cancelled = self.client.post('/api/v1/confirm', json={
            'confirmation_id': confirmation_id, 'device_id': 'mobile-a', 'confirmed': False
        })
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()['status'], 'cancelled')

        replay = self.client.post('/api/v1/confirm', json={
            'confirmation_id': confirmation_id, 'device_id': 'mobile-a', 'confirmed': True
        })
        self.assertEqual(replay.status_code, 404)

    def test_calendar_event_write_uses_one_use_confirmation_token(self):
        response = self.client.post('/api/v1/workspace/calendar/events', json={
            'summary': 'Test meeting', 'start': '2026-11-01T10:00:00+05:30',
            'end': '2026-11-01T10:30:00+05:30', 'device_id': 'calendar-client',
        })
        self.assertEqual(response.status_code, 200)
        challenge = response.json()
        self.assertEqual(challenge['status'], 'confirmation_required')
        self.assertEqual(challenge['preview']['summary'], 'Test meeting')
        with patch('visionguide.api_server.calendar_create_event', return_value={'id': 'event1', 'summary': 'Test meeting'}):
            executed = self.client.post('/api/v1/confirm', json={
                'confirmation_id': challenge['confirmation_id'], 'device_id': 'calendar-client', 'confirmed': True,
            })
        self.assertEqual(executed.status_code, 200)
        self.assertEqual(executed.json()['status'], 'executed')
        replay = self.client.post('/api/v1/confirm', json={
            'confirmation_id': challenge['confirmation_id'], 'device_id': 'calendar-client', 'confirmed': True,
        })
        self.assertEqual(replay.status_code, 404)

    def test_gmail_draft_send_returns_preview_and_requires_token_confirmation(self):
        preview = {'draft_id': 'draft1', 'to': 'person@example.com', 'subject': 'Review',
                   'body': 'Please review this draft.', 'fingerprint': 'abc123'}
        with patch('visionguide.api_server.gmail_draft_preview', return_value=preview):
            response = self.client.post('/api/v1/workspace/gmail/drafts/draft1/send', json={'device_id': 'gmail-client'})
        self.assertEqual(response.status_code, 200)
        challenge = response.json()
        self.assertEqual(challenge['status'], 'confirmation_required')
        self.assertEqual(challenge['preview']['to'], 'person@example.com')
        with patch('visionguide.api_server.gmail_send_draft', return_value={'id': 'sent1', 'status': 'sent'}) as send:
            executed = self.client.post('/api/v1/confirm', json={
                'confirmation_id': challenge['confirmation_id'], 'device_id': 'gmail-client', 'confirmed': True,
            })
        self.assertEqual(executed.status_code, 200)
        self.assertEqual(executed.json()['status'], 'executed')
        send.assert_called_once_with('draft1', confirmed=True, expected_fingerprint='abc123')

    def test_timer_api_create_and_cancel(self):
        response = self.client.post('/api/v1/timers', json={'seconds': 120, 'label': 'api test'})
        self.assertEqual(response.status_code, 200)
        timer_id = response.json()['id']
        cancelled = self.client.delete(f'/api/v1/timers/{timer_id}')
        self.assertTrue(cancelled.json()['cancelled'])


if __name__ == '__main__':
    unittest.main()
