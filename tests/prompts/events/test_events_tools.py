"""Tests for the EventsPrompts class."""
import unittest

from src.prompts import PROMPT_REGISTRY
from src.prompts.events.events_tools import EventsPrompts


class TestEventsPrompts(unittest.TestCase):
    """Test cases for the EventsPrompts class."""

    def test_get_event_registered(self):
        """Test that get_event is registered in the prompt registry."""
        # The registry contains staticmethod objects, so we need to unwrap them
        func = EventsPrompts.get_event
        self.assertTrue(any(
            getattr(item, '__func__', item) == func
            for item in PROMPT_REGISTRY
        ))

    def test_get_kubernetes_info_events_registered(self):
        """Test that get_kubernetes_info_events is registered in the prompt registry."""
        # The registry contains staticmethod objects, so we need to unwrap them
        func = EventsPrompts.get_kubernetes_info_events
        self.assertTrue(any(
            getattr(item, '__func__', item) == func
            for item in PROMPT_REGISTRY
        ))

    def test_get_agent_monitoring_events_registered(self):
        """Test that get_agent_monitoring_events is registered in the prompt registry."""
        # The registry contains staticmethod objects, so we need to unwrap them
        func = EventsPrompts.get_agent_monitoring_events
        self.assertTrue(any(
            getattr(item, '__func__', item) == func
            for item in PROMPT_REGISTRY
        ))

    def test_get_issues_registered(self):
        """Test that get_issues is registered in the prompt registry."""
        # The registry contains staticmethod objects, so we need to unwrap them
        func = EventsPrompts.get_issues
        self.assertTrue(any(
            getattr(item, '__func__', item) == func
            for item in PROMPT_REGISTRY
        ))

    def test_get_incidents_registered(self):
        """Test that get_incidents is registered in the prompt registry."""
        # The registry contains staticmethod objects, so we need to unwrap them
        func = EventsPrompts.get_incidents
        self.assertTrue(any(
            getattr(item, '__func__', item) == func
            for item in PROMPT_REGISTRY
        ))

    def test_get_changes_registered(self):
        """Test that get_changes is registered in the prompt registry."""
        # The registry contains staticmethod objects, so we need to unwrap them
        func = EventsPrompts.get_changes
        self.assertTrue(any(
            getattr(item, '__func__', item) == func
            for item in PROMPT_REGISTRY
        ))

    def test_get_events_by_ids_registered(self):
        """Test that get_events_by_ids is registered in the prompt registry."""
        # The registry contains staticmethod objects, so we need to unwrap them
        func = EventsPrompts.get_events_by_ids
        self.assertTrue(any(
            getattr(item, '__func__', item) == func
            for item in PROMPT_REGISTRY
        ))

    def test_get_prompts_returns_all_prompts(self):
        """Test that get_prompts returns all prompts defined in the class."""
        prompts = EventsPrompts.get_prompts()
        self.assertEqual(len(prompts), 7)
        self.assertEqual(prompts[0][0], 'get_event')
        self.assertEqual(prompts[1][0], 'get_kubernetes_info_events')
        self.assertEqual(prompts[2][0], 'get_agent_monitoring_events')
        self.assertEqual(prompts[3][0], 'get_issues')
        self.assertEqual(prompts[4][0], 'get_incidents')
        self.assertEqual(prompts[5][0], 'get_changes')
        self.assertEqual(prompts[6][0], 'get_events_by_ids')


if __name__ == '__main__':
    unittest.main()
