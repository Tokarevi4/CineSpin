import sys
import random
import math
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                               QVBoxLayout, QHBoxLayout, QLineEdit, 
                               QPushButton, QGroupBox, QListWidget, QMessageBox)
from PySide6.QtCore import Qt, QSize, QThread, Signal, QObject, Property, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QColor, QPainter, QFont, QPen, QPolygon, QPixmap

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 🎡 КАСТОМНЫЙ ВИДЖЕТ КОЛЕСА ФОРТУНЫ
class WheelWidget(QWidget):
    animation_finished = Signal(str)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(QSize(450, 450))
        self._rotation_angle = 0.0
        self.movies = []      # Полный список фильмов пользователя
        self.current_slots = [] # 12 фильмов, выбранных для текущего колеса
        
        self.colors = [
            QColor("#ff0043"), QColor("#00e5ff"), QColor("#ff00c8"),
            QColor("#00c030"), QColor("#ffaa00"), QColor("#7000ff"),
            QColor("#00ffd5"), QColor("#9dff00"), QColor("#ff5500")
        ]

    @Property(float)
    def rotation_angle(self):
        return self._rotation_angle

    @rotation_angle.setter
    def rotation_angle(self, value):
        self._rotation_angle = value
        self.update()

    def set_movies(self, movies_list):
        self.movies = movies_list
        self._rotation_angle = 0.0
        
        # Если фильмов много, берем случайные 12 штук, чтобы заполнить КОЛЕСО ПОЛНОСТЬЮ
        if len(self.movies) > 12:
            self.current_slots = random.sample(self.movies, 12)
        else:
            self.current_slots = list(self.movies)
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        rect = self.rect()
        size = min(rect.width(), rect.height()) - 60
        center_x = rect.width() // 2
        center_y = rect.height() // 2

        # Очистка фона
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#14181c"))
        painter.drawRect(rect)

        if not self.current_slots:
            painter.setPen(QColor("#9ab"))
            painter.setFont(QFont("Arial", 13, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Загрузите вотчлист\nили добавьте фильмы вручную")
            return

        display_count = len(self.current_slots)
        span_angle = 360.0 / display_count

        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self._rotation_angle)

        from PySide6.QtCore import QRect
        wheel_rect = QPoint(-size // 2, -size // 2)
        wheel_size = QSize(size, size)
        target_rect = QRect(wheel_rect, wheel_size)

        # 1. Рисуем цветные секторы
        for i in range(display_count):
            painter.setBrush(self.colors[i % len(self.colors)])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPie(target_rect, int(i * span_angle * 16), int(span_angle * 16))

        # 2. Рисуем адаптивный текст
        from PySide6.QtGui import QFontMetrics
        for i in range(display_count):
            painter.save()
            painter.rotate(i * span_angle + span_angle / 2)
            
            painter.setPen(QColor("#ffffff"))
            
            # Начальный (максимальный) размер шрифта в зависимости от масштаба колеса
            target_font_size = max(9, min(13, int(size / 32))) 
            text = self.current_slots[i]
            
            # Доступное место под текст (примерно 65% от радиуса, чтобы не вылезать за край)
            max_text_width = int((size / 2) * 0.65)
            
            # Цикл динамического уменьшения шрифта
            font = QFont("Arial", target_font_size, QFont.Weight.Bold)
            metrics = QFontMetrics(font)
            
            # Уменьшаем размер шрифта, пока текст не влезет или пока шрифт не станет минимальным (8)
            while metrics.horizontalAdvance(text) > max_text_width and target_font_size > 8:
                target_font_size -= 1
                font = QFont("Arial", target_font_size, QFont.Weight.Bold)
                metrics = QFontMetrics(font)
            
            # Если текст всё равно слишком длинный для минимального шрифта, красиво обрезаем его (добавляем ...)
            if metrics.horizontalAdvance(text) > max_text_width:
                text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max_text_width)
                
            painter.setFont(font)
            
            # Рисуем текст с безопасным отступом от центра
            current_font_size = painter.font().pointSize()
            painter.drawText(int(size * 0.16), current_font_size // 2, text)
            painter.restore()

        painter.restore()

        # Центральная ось
        painter.setBrush(QColor("#1e2328"))
        painter.setPen(QPen(QColor("#9ab"), 3))
        painter.drawEllipse(QPoint(center_x, center_y), 20, 20)

        # Стрелка сверху
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#14181c"), 2))
        arrow = QPolygon([
            QPoint(center_x, center_y - size // 2 - 5),
            QPoint(center_x - 12, center_y - size // 2 - 30),
            QPoint(center_x + 12, center_y - size // 2 - 30)
        ])
        painter.drawPolygon(arrow)


    def spin(self):
        if not self.current_slots: return
        
        display_count = len(self.current_slots)
        
        # Шаг 1: Выбираем случайного победителя ТОЛЬКО из тех, кто на колесе
        winner_index = random.randint(0, display_count - 1)
        self.winner_title = self.current_slots[winner_index]

        # Шаг 2: Математически выверенный расчет угла остановки под стрелку (на 90 градусов)
        sector_angle = 360.0 / display_count
        
        # Центр сектора победителя в полярных координатах
        target_sector_center = winner_index * sector_angle + sector_angle / 2
        
        # Корректируем смещение (90 градусов в Qt — это верх, а отсчет идет снизу вверх против часовой)
        # Добавляем 1800 градусов (5 полных оборотов) для долгого кручения
        final_angle = 270.0 - target_sector_center + 1800.0
        
        self.anim = QPropertyAnimation(self, b"rotation_angle")
        self.anim.setDuration(4500) # 4.5 секунды кручения
        self.anim.setStartValue(self._rotation_angle % 360)
        self.anim.setEndValue(final_angle)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic) # Красивое затухание
        
        self.anim.finished.connect(self.on_spin_end)
        self.anim.start()

    def on_spin_end(self):
        self.animation_finished.emit(self.winner_title)
        
        # Сразу после показа результата перемешиваем колесо заново из общего списка для следующего раунда
        self.set_movies(self.movies)


# 🧵 Класс-воркер для парсинга в отдельном фоновом потоке
class WatchlistWorker(QObject):
    # Сигналы для передачи результатов обратно в главный поток UI
    progress = Signal(str)      # Передает текст статуса (например, "Скачиваю страницу 2...")
    finished = Signal(list)     # Передает итоговый массив всех фильмов
    error = Signal(str)        # Передает сообщение об ошибке, если что-то пошло не так

    def __init__(self, username):
        super().__init__()
        self.username = username

    def run(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
        
        base_url = "https://letterboxd.com"
        movies_all = []
        page = 1

        while True:
            # 📌 Безопасная сборка ссылки обычным сложением строк без urljoin
            if page == 1:
                url = f"https://letterboxd.com{self.username}/watchlist/"
            else:
                url = f"https://letterboxd.com{self.username}/watchlist/page/{page}/"
            try:
                response = requests.get(url, headers=headers, timeout=10)
                
                # Если страница не найдена, значит мы дошли до конца (или юзера нет)
                if response.status_code == 404:
                    if page == 1:
                        self.error.emit(f"Пользователь '{self.username}' не найден!")
                        return
                    else:
                        break # Просто закончили пагинацию
                elif response.status_code != 200:
                    self.error.emit(f"Ошибка сервера Letterboxd (Код: {response.status_code})")
                    return

                soup = BeautifulSoup(response.text, "html.parser")
                posters = soup.find_all("div", class_="film-poster")
                
                # Если на странице вообще нет фильмов, останавливаемся
                if not posters:
                    break

                page_movies = []
                for poster in posters:
                    title = poster.get("data-film-name") or poster.get("data-film-slug")
                    if not title:
                        img_tag = poster.find("img")
                        if img_tag:
                            title = img_tag.get("alt") or img_tag.get("data-film-name")
                    if title:
                        page_movies.append(title)

                movies_all.extend(page_movies)

                # Проверяем, есть ли кнопка "Next" (следующая страница). Если её нет — это финал
                next_button = soup.find("a", class_="next")
                if not next_button:
                    break
                
                page += 1

            except requests.exceptions.RequestException as e:
                self.error.emit(f"Ошибка сети: {e}")
                return

        # Удаляем дубликаты с сохранением порядка
        movies_all = list(dict.fromkeys(movies_all))
        self.finished.emit(movies_all)


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
        
        manual_group = QGroupBox("Добавить фильм вручную")
        manual_layout = QVBoxLayout(manual_group)
        self.movie_input = QLineEdit()
        self.movie_input.setPlaceholderText("Название фильма...")
        self.add_manual_btn = QPushButton("Добавить")
        manual_layout.addWidget(self.movie_input)
        manual_layout.addWidget(self.add_manual_btn)
        
        parser_group = QGroupBox("Импорт из Letterboxd")
        parser_layout = QVBoxLayout(parser_group)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Никнейм пользователя...")
        self.parse_btn = QPushButton("Загрузить вотчлист")
        parser_layout.addWidget(self.username_input)
        parser_layout.addWidget(self.parse_btn)
        
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
        self.parse_btn.clicked.connect(self.start_async_parsing)
        self.spin_btn.clicked.connect(self.spin_the_wheel)
        self.wheel_area.animation_finished.connect(self.show_winner_popup)

    def add_movie_manually(self):
        movie_title = self.movie_input.text().strip()
        if movie_title:
            self.movies_list.addItem(movie_title)
            self.movie_input.clear()
            # Передаем обновленный список в колесо
            all_movies = [self.movies_list.item(i).text() for i in range(self.movies_list.count())]
            self.wheel_area.set_movies(all_movies)
        else:
            QMessageBox.warning(self, "Внимание", "Поле ввода пустое!")


    # 🛠 ЗАПУСК ФОНОВОГО ПОТОКА ДЛЯ ПАРСИНГА
    def start_async_parsing(self):
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Внимание", "Введите никнейм пользователя!")
            return
        
        self.parse_btn.setEnabled(False)

        # Создаем поток и объект-воркер
        self.thread = QThread()
        self.worker = WatchlistWorker(username)
        self.worker.moveToThread(self.thread)

        # Связываем сигналы воркера с методами интерфейса главного окна
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.update_parse_button_status)
        self.worker.error.connect(self.handle_parse_error)
        self.worker.finished.connect(self.handle_parse_success)
        
        # Гарантируем очистку памяти после завершения потока
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        # Стартуем поток
        self.thread.start()

    def update_parse_button_status(self, text):
        self.parse_btn.setText(text)

    def handle_parse_error(self, error_msg):
        QMessageBox.critical(self, "Ошибка загрузки", error_msg)
        self.reset_parse_button()
        self.thread.quit()

    def handle_parse_success(self, movies_found):
        self.movies_list.clear()
        if movies_found:
            self.movies_list.addItems(movies_found)
            # Загружаем спарсенные фильмы в колесо
            self.wheel_area.set_movies(movies_found)
            QMessageBox.information(self, "Готово", f"Колесо заряжено!\nВсего фильмов: {len(movies_found)}")
        else:
            QMessageBox.information(self, "Информация", "Вотчлист пуст.")
        self.reset_parse_button()

    def reset_parse_button(self):
        self.parse_btn.setText("Загрузить вотчлист")
        self.parse_btn.setEnabled(True)

    def spin_the_wheel(self):
        if self.movies_list.count() == 0:
            QMessageBox.warning(self, "Внимание", "Сначала добавьте фильмы!")
            return
        self.spin_btn.setEnabled(False) # Выключаем кнопку на время кручения
        self.wheel_area.spin()

    def show_winner_popup(self, winner_title):
        QMessageBox.information(self, "🎬 Фильм найден!", f"Сегодня смотрим:\n\n🎉 {winner_title} 🎉")
        self.spin_btn.setEnabled(True) # Включаем кнопку обратно

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
