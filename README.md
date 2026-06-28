# Healthcare Appointment Monitor

An automated appointment monitoring system that continuously checks doctor appointment availability and instantly notifies users through Telegram whenever new slots become available.

## Features

- Monitor specific doctors
- Automatic periodic checks
- Telegram instant notifications
- GitHub Actions deployment
- Configurable monitoring intervals
- Weekend-only monitoring support
- Lightweight and easy to configure

## Tech Stack

- Python
- Requests
- Telegram Bot API
- GitHub Actions
- JSON
- Cron Scheduling

## Project Structure

```
appointment-monitor/
├── main.py
├── config.py
├── requirements.txt
├── .github/
│   └── workflows/
├── utils/
├── README.md
└── .gitignore
```

## Installation

```bash
git clone https://github.com/Sur14srr/healthcare-appointment-monitor.git

cd healthcare-appointment-monitor

pip install -r requirements.txt

python main.py
```

## Configuration

Configure:

- Telegram Bot Token
- Chat ID
- Doctor ID
- Hospital Details
- Check Interval

## Future Improvements

- Web Dashboard
- Email Notifications
- SMS Alerts
- Multi-Doctor Monitoring
- Docker Support
- Database Integration
- Appointment History

## Author

Surendra Reddy
