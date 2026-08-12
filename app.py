import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                               QVBoxLayout, QHBoxLayout, QLineEdit, 
                               QPushButton, QGroupBox, QListWidget, QMessageBox)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPalette

import requests
from bs4 import BeautifulSoup

from urllib.parse import urljoin

class WheelWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(QSize(400, 400))
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#1e2328"))
        self.setPalette(palette)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Letterboxd Roulette")
        self.resize(900, 600)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # --- ЛЕВАЯ ПАНЕЛЬ ---
        side_panel = QWidget()
        side_panel.setFixedWidth(300)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(0, 0, 0, 0)
        
        # Блок А: Ручной ввод
        manual_group = QGroupBox("Добавить фильм вручную")
        manual_layout = QVBoxLayout(manual_group)
        self.movie_input = QLineEdit()
        self.movie_input.setPlaceholderText("Название фильма...")
        self.add_manual_btn = QPushButton("Добавить")
        manual_layout.addWidget(self.movie_input)
        manual_layout.addWidget(self.add_manual_btn)
        
        # Блок Б: Импорт из Letterboxd (Возвращаем к одной строке)
        parser_group = QGroupBox("Импорт из Letterboxd")
        parser_layout = QVBoxLayout(parser_group)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Никнейм пользователя...")
        self.parse_btn = QPushButton("Загрузить вотчлист")
        parser_layout.addWidget(self.username_input)
        parser_layout.addWidget(self.parse_btn)
        
        # Блок В: Список текущих лотов
        list_group = QGroupBox("Фильмы в рулетке")
        list_layout = QVBoxLayout(list_group)
        self.movies_list = QListWidget()
        self.spin_btn = QPushButton("КРУТИТЬ КОЛЕСО")
        self.spin_btn.setStyleSheet("background-color: #00c030; color: white; font-weight: bold; font-size: 14px; padding: 8px;")
        list_layout.addWidget(self.movies_list)
        list_layout.addWidget(self.spin_btn)
        
        side_layout.addWidget(manual_group)
        side_layout.addWidget(parser_group)
        side_layout.addWidget(list_group)
        
        # --- ПРАВАЯ ЗОНА ---
        self.wheel_area = WheelWidget()
        
        main_layout.addWidget(side_panel)
        main_layout.addWidget(self.wheel_area, stretch=1)

        self.add_manual_btn.clicked.connect(self.add_movie_manually)
        self.parse_btn.clicked.connect(self.parse_single_watchlist)
        self.spin_btn.clicked.connect(self.spin_wheel_placeholder)

    def add_movie_manually(self):
        movie_title = self.movie_input.text().strip()
        if movie_title:
            self.movies_list.addItem(movie_title)
            self.movie_input.clear()
        else:
            QMessageBox.warning(self, "Внимание", "Поле ввода пустое!")

    def parse_single_watchlist(self):
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Внимание", "Введите никнейм пользователя!")
            return
        
        self.parse_btn.setText("Загрузка...")
        self.parse_btn.setEnabled(False)
        QApplication.processEvents()

        # Полный набор заголовков, имитирующих реальный запрос современного браузера
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }
        
        from urllib.parse import urljoin
        base_url = "https://letterboxd.com/"
        url = urljoin(base_url, f"{username}/watchlist/")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 404:
                QMessageBox.critical(self, "Ошибка", f"Пользователь '{username}' не найден!")
                self.reset_parse_button()
                return
            elif response.status_code != 200:
                QMessageBox.critical(self, "Ошибка", f"Ошибка сервера Letterboxd (Код: {response.status_code})")
                self.reset_parse_button()
                return

            soup = BeautifulSoup(response.text, "html.parser")
            
            # 📌 ИЗМЕНЕНИЕ: Ищем контейнер фильма li, внутри которого Letterboxd хранит 
            # внутренний div с метаданными о фильме (класс 'poster' или 'film-poster')
            posters = soup.find_all("div", class_="film-poster")
            
            # Если не нашло 'film-poster', пробуем альтернативный поиск по li
            if not posters:
                posters = soup.find_all("li", class_="poster-container")

            movies_found = []
            for poster in posters:
                # Пытаемся вытащить название фильма из явного дата-атрибута тега div
                title = poster.get("data-film-slug") or poster.get("data-film-name")
                
                # Если в самом div названия нет, ищем вложенную картинку img
                if not title:
                    img_tag = poster.find("img")
                    if img_tag:
                        title = img_tag.get("alt") or img_tag.get("data-film-name")
                
                if title:
                    # Форматируем название: превращаем инди-слаги ('the-batman') обратно в читаемый вид
                    # или просто очищаем от лишних пробелов
                    formatted_title = title.replace("-", " ").title() if "-" in title and not poster.get("data-film-name") else title
                    movies_found.append(formatted_title)

            self.movies_list.clear()
            if movies_found:
                # Удаляем дубликаты, если они проскочили
                movies_found = list(dict.fromkeys(movies_found))
                self.movies_list.addItems(movies_found)
                QMessageBox.information(self, "Готово", f"Успешно загружено фильмов: {len(movies_found)}")
            else:
                QMessageBox.information(self, "Информация", 
                                        f"Не удалось извлечь фильмы. Вотчлист пуст, скрыт, или верстка изменилась.")

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Ошибка сети", f"Не удалось подключиться к Letterboxd: {e}")
        finally:
            self.reset_parse_button()

    def reset_parse_button(self):
        self.parse_btn.setText("Загрузить вотчлист")
        self.parse_btn.setEnabled(True)

    def spin_wheel_placeholder(self):
        count = self.movies_list.count()
        QMessageBox.information(self, "Рулетка", f"В колесе сейчас лотов: {count}. Готовы крутить!")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setStyleSheet("""
        QMainWindow { background-color: #14181c; }
        QGroupBox { color: #9ab; font-weight: bold; border: 1px solid #2c3440; margin-top: 12px; padding-top: 12px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }
        QLineEdit { background-color: #2c3440; color: #fff; border: 1px solid #445566; border-radius: 4px; padding: 6px; }
        QPushButton { background-color: #445566; color: #fff; border: none; border-radius: 4px; padding: 6px; font-weight: bold; }
        QPushButton:hover { background-color: #556677; }
        QListWidget { background-color: #1c252d; color: #9ab; border: 1px solid #2c3440; border-radius: 4px; }
    """)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
