# 🚀 SonicBook

**SonicBook** is a high-speed audiobook downloader designed specifically for audiobook streaming sites. It combines extreme download speeds with smart chapter splitting, making it the ultimate tool for audiobook enthusiasts.

## ✨ Features

-   **Extreme Speed:** Downloads book fragments in **16 concurrent streams**.
-   **Smart Chapter Splitting:** Automatically detects chapters and provides a **ZIP archive** with correctly named files.
-   **No Quality Loss:** Downloads original AAC/MP4 streams directly.
-   **Precision Tracking:** Real-time progress bar with 0.001% precision and fragment counter.
-   **Smart Naming:** Automatically parses "Author - Title" from the page.
-   **Modern UI:** Beautiful Dark/Light mode interface with multi-language support (EN/RU).
-   **Preview Mode:** See the list of chapters before you start downloading.

## 🛠️ Requirements

-   **Python 3.10+**
-   **FFmpeg** (installed and added to System PATH)
-   **Playwright** (browser engine for scraping)

## 🚀 Quick Start

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/shafranek-js/SonicBook.git
    cd SonicBook
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    playwright install chromium
    ```

3.  **Run the application:**
    ```bash
    python main.py
    ```

4.  Open your browser and navigate to `http://localhost:8000`.

## 📜 License

MIT License. Free for personal use.

---
Developed by [shafranek-js](https://github.com/shafranek-js)
