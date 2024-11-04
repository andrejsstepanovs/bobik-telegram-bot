import unittest
from datetime import datetime
from utils import get_entries_to_execute

class TestIsCronActive(unittest.TestCase):
    config = {
        "Weather": [
            {
                "schedule_human": "Run at 07:00 on weekdays",
                "schedule": "0 7 * * 1-5",
                "prompt": "Morning weather forecast for today."
            },
            {
                "schedule_human": "Run at 18:00 on weekdays",
                "schedule": "0 18 * * 1-5",
                "prompt": "Evening weather forecast for tomorrow."
            }
        ],
        "Kid": [
            {
                "schedule_human": "Run at 15:00 on weekdays",
                "schedule": "0 15 * * 1-5",
                "prompt": "Reminder about picking up kid from the school."
            }
        ],
        "Work": [
            {
                "schedule_human": "Run at 22:00 every Sunday, Monday, Tuesday, Wednesday, and Thursday.",
                "schedule": "0 22 * * 0-4",
                "prompt": "Evening briefing about breaking news and tomorrow planned events."
            }
        ],
        "Exercise": [
            {
                "schedule_human": "Run at 07:30 on jogging days",
                "schedule": "0 7 * * 1,2,3,5",
                "prompt": "Notification about weekly jogging quota."
            },
            {
                "schedule_human": "Run at 07:30 on gym days",
                "schedule": "0 7 * * 1,2,3,5",
                "prompt": "Notification about weekly gym quota."
            }
        ],
        "Gluten Sensitivity": [
            {
                "schedule_human": "Run at 08:00 every day",
                "schedule": "0 8 * * *",
                "prompt": "Reminder to balance gluten-rich foods with protein or healthy fats."
            }
        ],
        "News": [
            {
                "schedule_human": "Run at 12:00 every day",
                "schedule": "0 12 * * *",
                "prompt": "Update on the latest news, including finance, technology, health, and general news."
            }
        ],
        "Relaxation": [
            {
                "schedule_human": "Run at 19:00 on Friday",
                "schedule": "0 19 * * 5",
                "prompt": "Reminder to play piano for relaxation."
            }
        ],
        "Weekend": [
            {
                "schedule_human": "Run at 10:00 on Saturday",
                "schedule": "0 10 * * 6",
                "prompt": "Reminder about weekend plans."
            },
            {
                "schedule_human": "Run at 10:00 on Saturday",
                "schedule": "* * * * *",
                "prompt": "BLA."
            }
        ]
    }

    def test_is_cron_active(self):
        result = get_entries_to_execute(self.config)
        print(result)
        result = len(result) > 0
        self.assertEqual(result, False,
                         f"Failed")

if __name__ == '__main__':
    unittest.main()
