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

To run SonicBook correctly, you need the following system components and libraries:

1.  **Python 3.10+**: The core language for the backend.
2.  **FFmpeg**: Essential for parsing streams, splitting chapters, and converting audio. **Must be installed and added to your System PATH**.
    *   *Windows*: Can be installed via Winget (`winget install -e --id Gyan.FFmpeg`).
    *   *macOS*: `brew install ffmpeg`
    *   *Linux*: `sudo apt install ffmpeg`
3.  **Playwright (Chromium)**: A headless browser engine used for advanced scraping when direct HTML parsing fails.
4.  **HTTP/2 Support (`httpx[http2]`)**: Required for high-speed scraping of specific sites without getting blocked.
5.  **Aiofiles**: Used for efficient, non-blocking disk operations during downloads.

## 🚀 Quick Start

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/shafranek-js/SonicBook.git
    cd SonicBook
    ```

2.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install Playwright browser:**
    ```bash
    playwright install chromium
    ```

4.  **Run the application:**
    ```bash
    python main.py
    ```

5.  Open your browser and navigate to `http://localhost:8000`.

## 🏗️ Architecture & Development

For a detailed breakdown of the application architecture, exact dependencies, the current state of the codebase, and technical debt, please refer to the [Handoff Document](handoff.md).

## 📜 License

MIT License. Free for personal use.

---
Developed by [shafranek-js](https://github.com/shafranek-js)
