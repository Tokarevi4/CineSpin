> This project was vibecoded and is not an official Letterboxd app.
# CineSpin

An open-source cross-platform desktop application built with **Python** and **PySide6 (Qt)** that syncs with your **Letterboxd** profile, scrapes your watchlist asynchronously, and spins a beautifully rendered custom fortune wheel to pick a random movie for your evening.

## Features

- **Asynchronous Scraping (`QThread`)**: Scrapes the entire Letterboxd watchlist with full pagination in a background thread, keeping the user interface smooth and responsive (60 FPS) without freezes.
- **Vector-Based Custom UI**: The fortune wheel is fully drawn from scratch using Qt's `QPainter` layout engine with high-performance CSS-like styling (`QSS`).
- **Dynamic Text Scaling (`QFontMetrics`)**: Film titles automatically adjust their font size inside the wheel sectors depending on the window resolution or length of the title.
- **Manual & Automated Input**: Add custom movie titles manually or parse any public Letterboxd profile instantly.
- **TMDB Integration (Coming Soon)**: Fetches and displays the original movie poster when the wheel stops.

## Technical Stack

- **UI Framework**: PySide6 (Official Qt6 for Python)
- **Scraping Backend**: Requests + BeautifulSoup4
- **Concurrency**: Qt Event Loop & QThreads

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com
   cd CineSpin
   ```

2. **Create and activate a virtual environment:**
   - **Windows:**
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   - **macOS / Linux:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python test_app.py
   ```

## License

This project is open-source and available under the [MIT License](LICENSE). Inspired by the cinema aesthetics of Letterboxd. Created for educational and personal purposes.
