import sys  
import math
import requests
import random
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                               QVBoxLayout, QHBoxLayout, QLineEdit, 
                               QPushButton, QGroupBox, QListWidget, QMessageBox,
                               QLabel, QSlider, QTabWidget)
from PySide6.QtCore import Qt, QSize, QThread, Signal, QObject, Property, QPropertyAnimation, QEasingCurve, QPoint, QRect, QMimeData
from PySide6.QtGui import QColor, QPainter, QFont, QPen, QPolygon, QPixmap, QFontMetrics, QDrag

import requests
from bs4 import BeautifulSoup

BACKEND_URL = "https://cinespin-api.maxim-tokaref.workers.dev/movie"

class DragListWidget(QListWidget):
    """Кастомный список, который отдает чистый текст при Drag'n'Drop"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)

    def startDrag(self, supportedActions):
        # Получаем выделенный элемент списка
        item = self.currentItem()
        if not item:
            return

        # Создаем контейнер данных и принудительно пишем туда название фильма как чистый текст
        mime_data = QMimeData()
        mime_data.setText(item.text())

        # Создаем системный объект перетаскивания
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        
        # Запускаем перетаскивание
        drag.exec(supportedActions)

# 🎡 КАСТОМНЫЙ ВИДЖЕТ КОЛЕСА ФОРТУНЫ
class WheelWidget(QWidget):
    animation_finished = Signal(str)
    # Сигнал для уведомления GUI о том, что пул изменился (например, обновить счетчики на экране)
    pool_changed = Signal(int) 

    def __init__(self):
        super().__init__()
        self.setMinimumSize(QSize(450, 450))
        self._rotation_angle = 0.0
        self.movies = []
        self.current_slots = []
        self.spin_duration = 4500
        self.max_lots_limit = 50
        
        # Переменная для хранения отрендеренного статичного диска колеса
        self.wheel_buffer = None 
        
        self.colors = [
            QColor("#b3002f"), QColor("#0099aa"), QColor("#b3008c"),
            QColor("#008020"), QColor("#b37700"), QColor("#4c00b3"),
            QColor("#00b395"), QColor("#6eb300"), QColor("#b33c00")
        ]

        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            movie_title = event.mimeData().text()
            if self.add_slot_manually(movie_title):
                event.acceptProposedAction()



    def render_wheel_to_buffer(self):
        """Метод полностью отрисовывает диск колеса с текстом в картинку ОДИН раз"""
        rect = self.rect()
        size = min(rect.width(), rect.height()) - 60
        if size <= 0: size = 450
        
        from PySide6.QtGui import QPixmap, QPainterPath, QTransform
        import math
        
        self.wheel_buffer = QPixmap(size, size)
        self.wheel_buffer.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(self.wheel_buffer)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        display_count = len(self.current_slots)
        if display_count == 0:
            painter.end()
            return
            
        span_angle = 360.0 / display_count
        buffer_rect = QRect(0, 0, size, size)
        
        cx = size // 2
        cy = size // 2

        # 1. Рисуем цветные секторы в буфер
        for i in range(display_count):
            painter.setBrush(self.colors[i % len(self.colors)])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPie(buffer_rect, int(i * span_angle * 16), int(span_angle * 16))

        # 2. Рисуем адаптивный текст в буфер без save/restore
        for i in range(display_count):
            text = self.current_slots[i]
            target_font_size = max(6, min(12, int(size / 38)))
            
            min_distance_from_center = int(size * 0.18)
            max_text_width = int((size / 2) * 0.68)
            mid_radius = min_distance_from_center + (max_text_width / 2)
            sector_width_at_mid = 2 * mid_radius * math.sin(math.radians(span_angle / 2))
            
            font = QFont("Arial", target_font_size, QFont.Weight.Bold)
            metrics = QFontMetrics(font)
            
            while target_font_size > 6:
                if metrics.horizontalAdvance(text) <= max_text_width and metrics.height() * 1.2 <= sector_width_at_mid:
                    break
                target_font_size -= 1
                font = QFont("Arial", target_font_size, QFont.Weight.Bold)
                metrics = QFontMetrics(font)
                
            if metrics.horizontalAdvance(text) > max_text_width:
                text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max_text_width)
                
            current_font_metrics = QFontMetrics(font)
            text_y_offset = current_font_metrics.capHeight() // 2
            adaptive_pen_width = max(0.8, target_font_size * 0.13)
            
            # --- БЕЗОПАСНАЯ МАТРИЦА ВМЕСТО SAVE/RESTORE ---
            # Создаем чистую матрицу трансформации для конкретной надписи
            transform = QTransform()
            transform.translate(cx, cy)
            transform.rotate(i * span_angle + span_angle / 2)
            painter.setTransform(transform) # Применяем матрицу напрямую
            
            painter.setFont(font)
            
            path = QPainterPath()
            path.addText(min_distance_from_center, text_y_offset, font, text)
            
            pen = QPen(QColor("#14181c"), adaptive_pen_width)
            pen.setStyle(Qt.PenStyle.SolidLine)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            
            painter.setPen(QColor("#ffffff"))
            painter.drawText(min_distance_from_center, text_y_offset, text)
            
        # Сбрасываем трансформацию художника в дефолт перед закрытием
        painter.setTransform(QTransform())
        painter.end()


    def handle_quick_delete(self, item):
        """Хендлер быстрого удаления фильма по двойному клику"""
        movie_title = item.text()
        
        # Удаляем фильм из пула самого колеса (оно внутри перерисуется)
        self.wheel_widget.remove_slot_by_title(movie_title)
        
        # Удаляем элемент из визуального списка QListWidget на экране
        row = self.movie_list_widget.row(item)
        self.movie_list_widget.takeItem(row)

    @Property(float)
    def rotation_angle(self):
        return self._rotation_angle

    @rotation_angle.setter
    def rotation_angle(self, value):
        self._rotation_angle = value
        self.update()

    def set_movies(self, movies_list):
        """Инициализация списка при изменении ползунка или импорте"""
        self.movies = list(movies_list)
        self._rotation_angle = 0.0
        
        if self.max_lots_limit == 0:
            self.current_slots = []
        elif len(self.movies) > self.max_lots_limit:
            self.current_slots = random.sample(self.movies, self.max_lots_limit)
        else:
            self.current_slots = list(self.movies)

        # СБРАСЫВАЕМ КЭШ: Это заставит paintEvent перерисовать колесо под нового пользователя
        self.wheel_buffer = None 
        self.update()            
        self.pool_changed.emit(len(self.current_slots))



    def set_spin_duration(self, seconds: float):
        """Динамическая настройка времени вращения (вплоть до 60 секунд)"""
        # Переводим секунды в миллисекунды для QPropertyAnimation
        self.spin_duration = int(max(1.0, min(60.0, seconds)) * 1000)

    def remove_slot_by_title(self, title: str) -> bool:
        """Удаляет конкретный фильм из текущих слотов колеса"""
        if title in self.current_slots:
            self.current_slots.remove(title)
            
            # Если фильм удален вообще из программы, уберем его и из глобального списка
            if title in self.movies:
                self.movies.remove(title)
                
            self._rotation_angle = 0.0 # Сбрасываем угол
            self.wheel_buffer = None
            self.update()              # Принудительно вызываем paintEvent для перерисовки секторов
            self.pool_changed.emit(len(self.current_slots))
            return True
        return False


    def add_slot_manually(self, title: str) -> bool:
        """Добавляет фильм в пул колеса вручную при Drag'n'Drop"""
        # Если ползунок на нуле (колесо пустое), разрешаем добавить первый сектор
        if self.max_lots_limit == 0:
            self.max_lots_limit = 1
            
        # Если мы пытаемся добавить больше лотов, чем сейчас выставлено на ползунке
        if len(self.current_slots) >= self.max_lots_limit:
            if self.max_lots_limit < 50:
                self.max_lots_limit += 1 # Автоматически раздвигаем лимит на +1 (до 50)
            else:
                return False # Жесткий лимит колеса в 50 лотов превышен
            
        if title not in self.current_slots:
            self.current_slots.append(title)
            if title not in self.movies:
                self.movies.append(title)
            
            self._rotation_angle = 0.0
            self.wheel_buffer = None # СБРАСЫВАЕМ КЭШ-КАРТИНКУ, чтобы она перерисовалась
            self.update()
            
            # Отправляем сигнал главному окну, что размер пула изменился
            self.pool_changed.emit(len(self.current_slots))
            return True
        return False


    def resizeEvent(self, event):
        self.wheel_buffer = None
        super().resizeEvent(event)


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        rect = self.rect()
        center_x = rect.width() // 2
        center_y = rect.height() // 2
        size = min(rect.width(), rect.height()) - 60

        # Очистка фона
        painter.fillRect(rect, QColor("#14181c"))

        if not self.current_slots:
            painter.setPen(QColor("#9ab"))
            painter.setFont(QFont("Arial", 13, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Колесо пусто.\nДобавьте лоты!")
            return

        if self.wheel_buffer is None:
            self.render_wheel_to_buffer()

        # --- КРУЧЕНИЕ КОЛЕСА ЧЕРЕЗ МАТРИЦУ (БЕЗ SAVE/RESTORE) ---
        from PySide6.QtGui import QTransform
        
        wheel_transform = QTransform()
        wheel_transform.translate(center_x, center_y)
        wheel_transform.rotate(self._rotation_angle)
        painter.setTransform(wheel_transform)
        
        if self.wheel_buffer:
            painter.drawPixmap(-size // 2, -size // 2, self.wheel_buffer)
            
        # Важно! Сбрасываем матрицу обратно в дефолт, чтобы ось и стрелка рисовали на исходных местах
        painter.setTransform(QTransform())

        # Центральная ось (рисуется статично)
        painter.setBrush(QColor("#1e2328"))
        painter.setPen(QPen(QColor("#9ab"), 3))
        painter.drawEllipse(QPoint(center_x, center_y), 20, 20)

        # Стрелка сверху (рисуется статично)
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
        winner_index = random.randint(0, display_count - 1)
        self.winner_title = self.current_slots[winner_index]

        sector_angle = 360.0 / display_count
        target_sector_center = winner_index * sector_angle + sector_angle / 2
        
        # 📌 Читаем сохраненную переменную из self.spin_duration (если ее нет, ставим 4500 мс)
        duration_ms = getattr(self, 'spin_duration', 4500)
        
        # Переводим обратно в секунды для расчета динамического количества оборотов
        duration_seconds = duration_ms / 1000.0
        
        # 🚀 Масштабируем скорость: 2 полных оборота за каждую секунду времени вращения.
        # При 5 секундах будет 10 кругов, при 30 секундах — 60 кругов. 
        # Колесо всегда будет крутиться бешено и затормозит строго на последних 15-20% времени!
        total_rotations = int(duration_seconds * 2)
        
        final_angle = 270.0 - target_sector_center + (total_rotations * 360.0)
        
        self.anim = QPropertyAnimation(self, b"rotation_angle")
        
        # 📌 ПЕРЕДАЕМ ДИНАМИЧЕСКОЕ ВРЕМЯ В АНИМАТОР
        self.anim.setDuration(duration_ms) 
        
        self.anim.setStartValue(self._rotation_angle % 360)
        self.anim.setEndValue(final_angle)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuint) # Экспоненциальное торможение
        
        self.anim.finished.connect(self.on_spin_end)
        self.anim.start()


    def on_spin_end(self):
        # Просто отправляем название победителя во всплывающее окно
        self.animation_finished.emit(self.winner_title)

# Класс-воркер для парсинга в отдельном фоновом потоке
class WatchlistWorker(QObject):
    # Сигналы для передачи результатов обратно в главный поток UI
    progress = Signal(str)      # Передает текст статуса (например, "Скачиваю страницу 2...")
    finished = Signal(list)     # Передает итоговый массив всех фильмов
    error = Signal(str)        # Передает сообщение об ошибке, если что-то пошло не так

    # ИСПРАВЛЕНО: Добавлен именованный аргумент is_list_url
    def __init__(self, username, is_list_url=False):
        super().__init__()
        self.username = username  # В режиме списка здесь будет лежать полная ссылка
        self.is_list_url = is_list_url

    def run(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
        
        movies_all = []
        page = 1

        # Очищаем базовую ссылку от лишних слешей на конце для предсказуемой сборки пагинации
        base_url = self.username.rstrip('/')

        while True:
            # Безопасная сборка URL в зависимости от режима (Вотчлист или Список)
            if self.is_list_url:
                if page == 1:
                    url = f"{base_url}/"
                else:
                    url = f"{base_url}/page/{page}/"
            else:
                if page == 1:
                    url = f"https://letterboxd.com/{self.username}/watchlist/"
                else:
                    url = f"https://letterboxd.com/{self.username}/watchlist/page/{page}/"

            try:
                # Отправляем текущий статус на кнопку загрузки
                self.progress.emit(f"Скачивание страницы {page}...")
                response = requests.get(url, headers=headers, timeout=10)
                
                # Если страница не найдена, значит мы дошли до конца (или юзера/списка нет)
                if response.status_code == 404:
                    if page == 1:
                        # Адаптируем ошибку под открытую вкладку
                        if self.is_list_url:
                            self.error.emit("Список не найден! Проверьте правильность ссылки.")
                        else:
                            self.error.emit(f"Пользователь '{self.username}' не найден!")
                        return
                    else:
                        break # Просто закончили пагинацию страниц
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
        self.setWindowTitle("CineSpin")
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
        
        # --- ИМПОРТ ИЗ LETTERBOXD (ВКЛАДКИ) ---
        parser_group = QGroupBox("Импорт из Letterboxd")
        parser_group_layout = QVBoxLayout(parser_group)
        parser_group_layout.setContentsMargins(5, 10, 5, 5)
        
        # Создаем виджет вкладок
        # Создаем виджет вкладок с исправленными цветами фона
        self.import_tabs = QTabWidget()
        self.import_tabs.setStyleSheet("""
            QTabWidget::panel { 
                border: 1px solid #2c3440; 
                background-color: #14181c; /* Цвет панели подложки */
            }
            QWidget {
                background-color: #14181c; /* Принудительный цвет для содержимого вкладок */
            }
            QTabWidget::tab-bar { 
                left: 5px; 
            }
            QTabBar::tab { 
                background: #2c3440; 
                color: #9ab; 
                font-weight: bold; 
                padding: 6px 12px; 
                border-top-left-radius: 4px; 
                border-top-right-radius: 4px; 
            }
            QTabBar::tab:selected { 
                background: #445566; 
                color: #fff; 
            }
            QTabBar::tab:hover { 
                background: #354352; 
            }
        """)

        
        # Вкладка 1: Одиночный режим
        single_tab = QWidget()
        single_layout = QVBoxLayout(single_tab)
        single_layout.setContentsMargins(10, 10, 10, 10)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Никнейм пользователя...")
        single_layout.addWidget(self.username_input)
        single_layout.addStretch()
        
        # Вкладка 2: Мультиплеер (Пересечение)
        multi_tab = QWidget()
        multi_layout = QVBoxLayout(multi_tab)
        multi_layout.setContentsMargins(10, 10, 10, 10)
        self.multi_username_input = QLineEdit()
        self.multi_username_input.setPlaceholderText("Никнеймы через запятую (user1, user2)...")
        multi_layout.addWidget(self.multi_username_input)
        single_layout.addStretch()

        # Вкладка 3: Публичные списки
        list_url_tab = QWidget()
        list_url_layout = QVBoxLayout(list_url_tab)
        list_url_layout.setContentsMargins(10, 10, 10, 10)
        self.list_url_input = QLineEdit()
        self.list_url_input.setPlaceholderText("Ссылка на список Letterboxd...")
        list_url_layout.addWidget(self.list_url_input)
        single_layout.addStretch()
        
        # Добавляем вкладки в QTabWidget
        self.import_tabs.addTab(single_tab, "Один")
        self.import_tabs.addTab(multi_tab, "Несколько")
        self.import_tabs.addTab(list_url_tab, "Списки") 
        
        # Общая кнопка загрузки под вкладками
        self.parse_btn = QPushButton("Загрузить вотчлист")
        
        parser_group_layout.addWidget(self.import_tabs)
        parser_group_layout.addWidget(self.parse_btn)
        
        # Блок списка
        list_group = QGroupBox("Фильмы в рулетке")
        list_layout = QVBoxLayout(list_group)
        self.movies_list = DragListWidget()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по вотчлисту...")
        self.spin_btn = QPushButton("КРУТИТЬ КОЛЕСО")
        
        list_layout.addWidget(self.movies_list)
        list_layout.addWidget(self.search_input) 
        list_layout.addWidget(self.spin_btn)
        
        side_layout.addWidget(manual_group, stretch=0)
        side_layout.addWidget(parser_group, stretch=0)
        side_layout.addWidget(list_group, stretch=1)
        
        # --- ПРАВАЯ ЗОНА ---
        self.wheel_area = WheelWidget()
        
        # 1. Верхняя панель управления (Время прокрутки сверху справа)
        top_control_panel = QWidget()
        top_control_layout = QHBoxLayout(top_control_panel)
        top_control_layout.setContentsMargins(10, 5, 10, 5)
        
        time_label = QLabel("Время прокрутки:")
        time_label.setStyleSheet("color: #9ab; font-weight: bold;")
        
        self.time_input = QLineEdit()
        self.time_input.setText("4.5")  # Дефолтное значение
        self.time_input.setPlaceholderText("1-60")
        self.time_input.setFixedWidth(60)
        self.time_input.setStyleSheet("""
            QLineEdit { 
                background-color: #2c3440; 
                color: #fff; 
                border: 1px solid #445566; 
                border-radius: 4px; 
                padding: 4px; 
                font-weight: bold;
                text-align: center;
            }
        """)
        
        time_sec_label = QLabel("сек.")
        time_sec_label.setStyleSheet("color: #9ab; font-weight: bold;")
        
        # ПРИМЕНЯЕМ СТРЕТЧ: сдвигаем элементы времени в самый правый край
        top_control_layout.addStretch() 
        top_control_layout.addWidget(time_label)
        top_control_layout.addWidget(self.time_input)
        top_control_layout.addWidget(time_sec_label)
        
        # 2. Нижняя панель управления (Ползунок количества слотов)
        slider_group = QWidget()
        slider_layout = QHBoxLayout(slider_group)
        slider_layout.setContentsMargins(10, 0, 10, 10)
        
        self.size_label = QLabel("Слотов на колесе: 12")
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(0, 50)  
        self.size_slider.setValue(12)      
        self.size_slider.setEnabled(False) 
        
        self.size_slider.setStyleSheet("""
            QSlider::groove:horizontal { border: 1px solid #445566; height: 6px; background: #2c3440; border-radius: 3px; }
            QSlider::handle:horizontal { background: #00c030; border: none; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
            QSlider::handle:horizontal:hover { background: #00e5ff; }
            QSlider::handle:horizontal:disabled { background: #445566; }
        """)
        
        slider_layout.addWidget(self.size_label)
        slider_layout.addWidget(self.size_slider)
        
        # 3. Собираем всю правую панель по вертикали (Топ-панель -> Колесо -> Слайдер)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        right_layout.addWidget(top_control_panel) # Поля времени теперь СВЕРХУ
        right_layout.addWidget(self.wheel_area, stretch=1)
        right_layout.addWidget(slider_group) 
        
        # 4. Добавляем готовые панели в главный горизонтальный слой
        main_layout.addWidget(side_panel)
        main_layout.addWidget(right_panel, stretch=2)

        # ==========================================================
        # СИГНАЛЫ 
        # ==========================================================
        # Логика кнопок управления
        self.add_manual_btn.clicked.connect(self.add_movie_manually)
        self.parse_btn.clicked.connect(self.start_async_parsing)
        self.spin_btn.clicked.connect(self.spin_the_wheel)
        
        # Логика взаимодействия с колесом
        self.wheel_area.animation_finished.connect(self.show_winner_popup)
        self.movies_list.itemDoubleClicked.connect(self.handle_quick_delete)
        
        # Настройка и синхронизация ползунка количества слотов
        self.size_slider.valueChanged.connect(self.handle_wheel_size_change)
        self.wheel_area.pool_changed.connect(self.sync_interface_with_wheel)
        
        # Динамический поиск по вотчлисту
        self.search_input.textChanged.connect(self.filter_movies_list)
        
        # Валидация времени прокрутки (ввод с клавиатуры)
        self.time_input.editingFinished.connect(self.handle_time_input_change)
        
        # Инициализируем стартовое время при запуске приложения
        self.handle_time_input_change()

    def filter_movies_list(self, text):
        """Динамически скрывает или показывает фильмы в зависимости от ввода"""
        search_term = text.strip().lower() # Приводим к нижнему регистру для регистронезависимого поиска
        
        # Проходим циклом по всем элементам QListWidget
        for i in range(self.movies_list.count()):
            item = self.movies_list.item(i)
            movie_title = item.text().lower()
            
            # Если поисковый запрос пустой ИЛИ название фильма содержит этот запрос
            if not search_term or search_term in movie_title:
                item.setHidden(False) # Показываем строку
            else:
                item.setHidden(True)  # Скрываем строку

    def sync_interface_with_wheel(self, current_pool_size):
        """Синхронизирует ползунок и UI при Drag'n'Drop изменениях на колесе"""
        # Временно блокируем сигналы ползунка, чтобы не вызвать зацикливание обновления
        self.size_slider.blockSignals(True)
        
        # Автоматически сдвигаем ползунок под реальное число секторов на колесе
        self.size_slider.setValue(current_pool_size)
        self.size_label.setText(f"Слотов на колесе: {current_pool_size}")
        
        # Если на колесо добавили первый фильм, активируем ползунок для управления
        if current_pool_size > 0:
            self.size_slider.setEnabled(True)
            
        self.size_slider.blockSignals(False)

        # Проверяем левый список (на случай, если фильма там почему-то не было)
        existing_items = [self.movies_list.item(i).text() for i in range(self.movies_list.count())]
        for movie in self.wheel_area.current_slots:
            if movie not in existing_items:
                self.movies_list.addItem(movie)


    # Добавляем внутрь класса MainWindow
    def handle_quick_delete(self, item):
        """Хендлер быстрого удаления фильма по двойному клику"""
        movie_title = item.text()
        
        # Удаляем фильм из пула самого колеса (оно внутри перерисуется)
        self.wheel_area.remove_slot_by_title(movie_title)
        
        # ИСПРАВЛЕНО: Удаляем элемент из правильного виджета списка
        row = self.movies_list.row(item)
        self.movies_list.takeItem(row)

    def handle_wheel_size_change(self, value):
        """Хендлер перемещения ползунка размера колеса"""
        # 1. Обновляем текст счетчика рядом с ползунком
        self.size_label.setText(f"Слотов на колесе: {value}")
        
        # 2. Передаем новый максимальный лимит в колесо
        self.wheel_area.max_lots_limit = value
        
        # 3. Если в программе уже есть глобальный список фильмов (Watchlist)
        if self.wheel_area.movies:
            # Перевыбираем фильмы внутри колеса под новое количество слотов
            self.wheel_area.set_movies(self.wheel_area.movies)
            
            # УДАЛЕНО: Мы больше не вызываем self.movies_list.clear()!
            # Левый список сохраняет все загруженные фильмы в целости и сохранности.

    def handle_time_input_change(self):
        """Обрабатывает ввод времени вращения с клавиатуры и защищает от ошибок"""
        raw_text = self.time_input.text().strip()
        
        # Заменяем запятую на точку на случай, если пользователь ввел "4,5" вместо "4.5"
        raw_text = raw_text.replace(",", ".")
        
        try:
            # Пытаемся преобразовать текст в число
            seconds = float(raw_text)
            
            # Проверяем диапазон (вплоть до минуты = 60 секунд)
            if seconds < 1.0:
                QMessageBox.warning(self, "Внимание", "Минимальное время вращения — 1 секунда.")
                seconds = 1.0
                self.time_input.setText("1.0")
            elif seconds > 60.0:
                QMessageBox.warning(self, "Внимание", "Максимальное время вращения — 60 секунд (1 минута).")
                seconds = 60.0
                self.time_input.setText("60.0")
                
            # Передаем валидное значение в метод колеса
            # Наш WheelWidget принимает секунды и переводит во внутренние миллисекунды
            self.wheel_area.set_spin_duration(seconds)
            
        except ValueError:
            # Если перевод в float упал (пользователь ввел буквы, пустую строку или спецсимволы)
            QMessageBox.critical(self, "Ошибка ввода", "Введите корректное число секунд (например: 5 или 4.5)")
            
            # Сбрасываем интерфейс и логику на безопасное дефолтное значение
            self.time_input.setText("4.5")
            self.wheel_area.set_spin_duration(4.5)

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
        current_tab_index = self.import_tabs.currentIndex()
        is_list_url = False
        
        if current_tab_index == 0:
            # Режим "Один"
            username = self.username_input.text().strip()
            if not username:
                QMessageBox.warning(self, "Внимание", "Введите никнейм пользователя!")
                return
            self.users_to_parse = [username]
            
        elif current_tab_index == 1:
            # Режим "Несколько"
            raw_input = self.multi_username_input.text().strip()
            if not raw_input:
                QMessageBox.warning(self, "Внимание", "Введите никнеймы через запятую!")
                return
            self.users_to_parse = [u.strip() for u in raw_input.split(",") if u.strip()]
            if len(self.users_to_parse) < 2:
                QMessageBox.warning(self, "Внимание", "Для кооператива нужно минимум 2 пользователя!")
                return
                
        else:
            # --- РЕЖИМ СВИСКА ПО ССЫЛКЕ ---
            url = self.list_url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "Внимание", "Вставьте ссылку на список Letterboxd!")
                return
            if "://letterboxd.com" not in url or "/list/" not in url:
                QMessageBox.warning(self, "Ошибка ссылки", "Ссылка должна вести на список Letterboxd (содержать /list/)!")
                return
                
            self.users_to_parse = [url]
            is_list_url = True

        self.multi_parsed_results = []
        self.current_user_index = 0
        
        self.parse_btn.setEnabled(False)
        self.parse_btn.setStyleSheet("background-color: #2c3440; color: #556677; font-weight: bold;")
        
        self.parse_next_user(is_list_url)

    def parse_next_user(self, is_list_url=False):
        if self.current_user_index < len(self.users_to_parse):
            target = self.users_to_parse[self.current_user_index]
            
            if is_list_url:
                self.parse_btn.setText("Скачивание списка...")
            else:
                self.parse_btn.setText(f"Скачивание {target}...")
            
            self.thread = QThread()
            # Передаем флаг в воркер
            self.worker = WatchlistWorker(target, is_list_url=is_list_url)
            self.worker.moveToThread(self.thread)

            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.update_parse_button_status)
            self.worker.error.connect(self.handle_parse_error)
            self.worker.finished.connect(self.handle_single_user_success)
            
            self.worker.finished.connect(self.thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)
            
            # Используем lambda, чтобы безопасно передать флаг в метод остановки потока
            self.thread.finished.connect(lambda: self.on_current_thread_fully_stopped(is_list_url))
            self.thread.finished.connect(self.thread.deleteLater)

            self.thread.start()
        else:
            self.finalize_multiplayer_intersection()

    def on_current_thread_fully_stopped(self, is_list_url):
        self.current_user_index += 1
        self.parse_next_user(is_list_url)


    def handle_single_user_success(self, movies_found):
        """Вызывается, когда воркер закончил парсить текущего пользователя"""
        # Сохраняем результат в виде множества
        self.multi_parsed_results.append(set(movies_found))
        # Больше здесь ничего делать не нужно — закрытие потока само запустит следующего юзера


    def finalize_multiplayer_intersection(self):
        """Финальный метод: пересекает все вотчлисты по принципу логического И"""
        if not self.multi_parsed_results:
            self.reset_parse_button()
            return
            
        # ИСПРАВЛЕНО: Явно берем копию множества первого пользователя (.copy())
        intersection_set = self.multi_parsed_results[0].copy()
        
        # Пересекаем со всеми остальными пользователями
        for user_set in self.multi_parsed_results[1:]:
            intersection_set = intersection_set & user_set
            
        final_movies = sorted(list(intersection_set))
        
        # Выгружаем результат
        self.handle_parse_success(final_movies)



    def update_parse_button_status(self, text):
        # Метод будет выводить динамический статус из воркера (например: "Загрузка: стр. 1")
        self.parse_btn.setText(text)

    def handle_parse_error(self, error_msg):
        QMessageBox.critical(self, "Ошибка загрузки", error_msg)
        self.reset_parse_button()
        
        # Гасим текущий запущенный поток, если он активен
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.quit()


    def handle_parse_success(self, movies_found):
        self.search_input.clear()
        self.list_url_input.clear()
        self.movies_list.clear()
        
        if movies_found:
            max_available = min(50, len(movies_found))
            start_val = min(12, max_available)
            
            self.wheel_area.max_lots_limit = start_val
            self.wheel_area.wheel_buffer = None
            
            self.size_slider.blockSignals(True)
            self.size_slider.setRange(0, max_available)
            self.size_slider.setValue(start_val)
            self.size_label.setText(f"Слотов на колесе: {start_val}")
            self.size_slider.setEnabled(True)
            self.size_slider.blockSignals(False)
            
            self.movies_list.addItems(movies_found) 
            self.wheel_area.set_movies(movies_found)
            
            # --- ИСПРАВЛЕНИЕ: Динамический текст уведомления в зависимости от вкладки ---
            current_tab = self.import_tabs.currentIndex()
            if current_tab == 0:
                msg_text = f"Колесо заряжено!\nВсего загружено из вотчлиста: {len(movies_found)}"
            elif current_tab == 1:
                msg_text = f"Колесо заряжено!\nВсего пересечений: {len(movies_found)}"
            else:
                msg_text = f"Колесо заряжено!\nВсего загружено из списка: {len(movies_found)}"
                
            QMessageBox.information(self, "Готово", msg_text)
            # ----------------=========================================================
            
        else:
            self.wheel_area.max_lots_limit = 0
            self.wheel_area.wheel_buffer = None
            self.wheel_area.set_movies([])
            
            self.size_slider.blockSignals(True)
            self.size_slider.setRange(0, 0)
            self.size_slider.setValue(0)
            self.size_label.setText("Слотов на колесе: 0")
            self.size_slider.setEnabled(False)
            self.size_slider.blockSignals(False)
            
            # Динамический текст ошибки для пустых результатов
            current_tab = self.import_tabs.currentIndex()
            if current_tab == 1:
                QMessageBox.information(self, "Информация", "Общих фильмов не найдено.")
            elif current_tab == 2:
                QMessageBox.information(self, "Информация", "В указанном списке нет фильмов.")
            else:
                QMessageBox.information(self, "Информация", "Вотчлист пуст.")
            
        self.reset_parse_button()


    def reset_parse_button(self):
        # 2. Возвращаем кнопке её исходный текст, состояние и дефолтный стиль
        self.parse_btn.setText("Загрузить вотчлист")
        self.parse_btn.setEnabled(True)
        # Сброс стилей на пустую строку вернет глобальный stylesheet приложения (из блока if __name__ == "__main__")
        self.parse_btn.setStyleSheet("") 


    def spin_the_wheel(self):
        if self.movies_list.count() == 0:
            QMessageBox.warning(self, "Внимание", "Сначала добавьте фильмы!")
            return
        self.spin_btn.setEnabled(False)
        
        self.wheel_area.spin() 



    def fetch_movie_poster(self, movie_title):
        clean_title = movie_title.replace("-", " ").strip()

        if not clean_title:
            print("Название фильма пустое.")
            return None

        params = {
            "title": clean_title,
        }

        try:
            # Запрашиваем информацию о фильме через Cloudflare Worker
            response = requests.get(
                BACKEND_URL,
                params=params,
                timeout=10,
            )

            print(f"CineSpin API status: {response.status_code}")

            response.raise_for_status()

            data = response.json()

            poster_url = data.get("poster_url")

            if not poster_url:
                print(
                    f"У фильма '{clean_title}' "
                    "отсутствует постер."
                )
                return None

            print(f"Загрузка постера: {poster_url}")

            # Загружаем непосредственно изображение
            image_response = requests.get(
                poster_url,
                timeout=10,
            )

            image_response.raise_for_status()

            pixmap = QPixmap()

            if pixmap.loadFromData(image_response.content):
                print(
                    f"Постер успешно загружен: "
                    f"{clean_title}"
                )
                return pixmap

            print(
                "QPixmap не смог загрузить "
                "изображение."
            )

        except requests.exceptions.Timeout:
            print(
                "Превышено время ожидания "
                "CineSpin API/TMDB."
            )

        except requests.exceptions.ConnectionError:
            print(
                "Не удалось подключиться "
                "к CineSpin API."
            )

        except requests.exceptions.HTTPError as exc:
            print(
                f"HTTP ошибка CineSpin API: {exc}"
            )

        except ValueError as exc:
            print(
                f"Ошибка обработки JSON: {exc}"
            )

        except Exception as exc:
            print(
                f"Неожиданная ошибка "
                f"при загрузке постера: {exc}"
            )

        return None

    def show_winner_popup(self, winner_title):
        self.spin_btn.setText("Загрузка обложки...")
        QApplication.processEvents()

        # Скачиваем постер напрямую в объект QPixmap
        poster_pixmap = self.fetch_movie_poster(winner_title)

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("🎬 Фильм на вечер найден!")

        # СБРОС СТИЛЕЙ для иконки
        msg_box.setIcon(QMessageBox.Icon.NoIcon)

        # Если картинка скачалась, принудительно задаем ее размер и передаем в QMessageBox
        if poster_pixmap and not poster_pixmap.isNull():
            scaled_pixmap = poster_pixmap.scaled(
                180,
                270,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            msg_box.setIconPixmap(scaled_pixmap)
            msg_box.setText(f"Сегодня вы смотрите:\n\n🎉  {winner_title}  🎉")
        else:
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setText(f"Сегодня вы смотрите:\n\n🎉 {winner_title} 🎉")

        # Индивидуальный стиль
        msg_box.setStyleSheet("""
            QMessageBox { background-color: #1c252d; border: 1px solid #2c3440; }
            QMessageBox QLabel { color: #ffffff; font-size: 14px; font-weight: bold; font-family: 'Arial'; }
            QPushButton { background-color: #00c030; color: white; font-weight: bold; padding: 6px 25px; border-radius: 4px; border: none; min-width: 80px; }
            QPushButton:hover { background-color: #00e035; }
        """)

        self.spin_btn.setText("КРУТИТЬ КОЛЕСО")
        self.spin_btn.setEnabled(True)
        msg_box.exec()



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
