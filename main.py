import csv
import os
import sqlite3
import sys

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QIcon, QIntValidator, QDoubleValidator
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWidgets import QCompleter
from PyQt5.QtWidgets import (
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
    QStyledItemDelegate,
)

from app_design import Ui_MainWindow


class ReadOnlyDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        return None


class RestaurantApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.orderIdColumn = 0

        self.connection = sqlite3.connect("restaurant.db")
        self.cursor = self.connection.cursor()

        self.create_tables()

        self.init_ui()

        self.price_input.editingFinished.connect(self.validate_price)
        self.quantity_input.editingFinished.connect(self.validate_quantity)

        self.reports_table.setItemDelegateForColumn(0, ReadOnlyDelegate())
        self.menu_table.setItemDelegateForColumn(0, ReadOnlyDelegate())

    def validate_price(self):
        self.validate_number_input(self.price_input, "Цена")

    def validate_quantity(self):
        self.validate_number_input(self.quantity_input, "Количество")

    def validate_number_input(self, line_edit, field_name):
        try:
            value = int(line_edit.text())
            if value < 0:
                raise ValueError("Значение должно быть неотрицательным целым числом.")
        except ValueError:
            QMessageBox.warning(
                self,
                "Ошибка ввода",
                f"Недопустимое значение {field_name}. Введите неотрицательное целое число.",
            )
            line_edit.clear()

    def delete_selected_rows(self):
        if self.reports_table.selectionModel().hasSelection():
            active_table = self.reports_table
        elif self.menu_table.selectionModel().hasSelection():
            active_table = self.menu_table
        else:

            return

        selected_rows = set(
            index.row() for index in active_table.selectionModel().selectedRows()
        )

        for row in sorted(selected_rows, reverse=True):
            if active_table == self.reports_table:
                order_id = int(active_table.item(row, 0).text())
                self.cursor.execute(
                    "DELETE FROM Orders WHERE order_id = ?", (order_id,)
                )
            elif active_table == self.menu_table:
                dish_id = int(active_table.item(row, 0).text())
                self.cursor.execute("DELETE FROM Menu WHERE dish_id = ?", (dish_id,))

            self.connection.commit()

        if active_table == self.reports_table:
            self.generate_reports()
        elif active_table == self.menu_table:
            self.generate_menu_table()

    def create_tables(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Menu (
                dish_id INTEGER PRIMARY KEY,
                dish_name TEXT NOT NULL,
                price REAL NOT NULL,
                image_path TEXT
            )
        """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Orders (
                order_id INTEGER PRIMARY KEY,
                table_number INTEGER NOT NULL,
                dish_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                special_requests TEXT,
                FOREIGN KEY (dish_id) REFERENCES Menu (dish_id)
            )
        """
        )

        self.connection.commit()

    def init_ui(self):
        self.export_button.clicked.connect(self.export_table_to_file)
        self.dish_line_edit.setCompleter(QCompleter())

        self.reports_table.setItemDelegateForColumn(
            self.orderIdColumn, ReadOnlyDelegate()
        )

        self.dish_line_edit.textChanged.connect(self.update_dish_auto_completion)
        self.select_image_button.clicked.connect(self.select_image)
        self.add_dish_button.clicked.connect(self.add_dish)
        self.add_order_button.clicked.connect(self.add_order)

        self.delete_button.clicked.connect(self.delete_selected_rows)

        self.populate_dish_auto_completion()

        price_validator = QDoubleValidator()
        quantity_validator = QIntValidator()

        self.price_input.setValidator(price_validator)
        self.quantity_input.setValidator(quantity_validator)

        self.setWindowTitle("Система управления рестораном")
        self.setGeometry(100, 100, 600, 500)
        self.show()
        self.generate_reports()
        self.generate_menu_table()

        self.reports_table.itemDoubleClicked.connect(self.open_image)
        self.menu_table.itemDoubleClicked.connect(self.open_image)

        self.reports_table.itemChanged.connect(self.handle_item_changed)
        self.menu_table.itemChanged.connect(self.handle_item_changed)

    def open_image(self, item):

        if item.column() == 5:

            image_path = item.text()

            if image_path:
                os.system(f"start {image_path}")

    def export_table_to_file(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        menu_file_name, menu_selected_filter = QFileDialog.getSaveFileName(
            self,
            "Сохранить меню",
            "",
            "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)",
            options=options,
        )
        orders_file_name, orders_selected_filter = QFileDialog.getSaveFileName(
            self,
            "Сохранить заказы",
            "",
            "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)",
            options=options,
        )

        if menu_file_name and orders_file_name:
            try:
                if menu_selected_filter == "CSV Files (*.csv)":
                    self.export_table_to_csv(menu_file_name + ".csv", self.menu_table)
                elif menu_selected_filter == "Text Files (*.txt)":
                    self.export_table_to_txt(menu_file_name + ".txt", self.menu_table)

                if orders_selected_filter == "CSV Files (*.csv)":
                    self.export_table_to_csv(
                        orders_file_name + ".csv", self.reports_table
                    )
                elif orders_selected_filter == "Text Files (*.txt)":
                    self.export_table_to_txt(
                        orders_file_name + ".txt", self.reports_table
                    )

                QMessageBox.information(self, "Успех", "Файлы успешно сохранены.")
            except Exception as e:
                QMessageBox.warning(
                    self, "Ошибка", f"Ошибка при сохранении файлов: {str(e)}"
                )

    def export_table_to_csv(self, file_name, table):
        with open(file_name, "w", newline="", encoding="utf-8") as csvfile:
            csv_writer = csv.writer(
                csvfile, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
            )
            header = [
                table.horizontalHeaderItem(i).text() for i in range(table.columnCount())
            ]
            csv_writer.writerow(header)

            for row in range(table.rowCount()):
                csv_row = [
                    table.item(row, col).text() for col in range(table.columnCount())
                ]
                csv_writer.writerow(csv_row)

    def export_table_to_txt(self, file_name, table):
        with open(file_name, "w", encoding="utf-8") as txtfile:
            for row in range(table.rowCount()):
                txt_row = "\t".join(
                    table.item(row, col).text() for col in range(table.columnCount())
                )
                txtfile.write(txt_row + "\n")

    def populate_dish_auto_completion(self):
        self.cursor.execute("SELECT dish_name FROM Menu")
        dishes = [dish[0] for dish in self.cursor.fetchall()]

        completer = QCompleter(dishes, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.dish_line_edit.setCompleter(completer)

    def update_dish_auto_completion(self):
        self.populate_dish_auto_completion()

    def select_image(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        image_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать файл изображения",
            "",
            "Файлы изображений (*.png *.jpg *.bmp *.gif);;Все файлы (*)",
            options=options,
        )

        if image_path:
            self.image_path_input.setText(image_path)

    def add_dish(self):
        inputs = [self.dish_name_input, self.price_input, self.image_path_input]
        data = [i.text() for i in inputs]

        if not all(data):
            QMessageBox.warning(
                self, "Ошибка", "Заполните все поля перед добавлением блюда."
            )
            return

        try:
            self.cursor.execute(
                "INSERT INTO Menu (dish_name, price, image_path) VALUES (?, ?, ?)",
                (data[0], float(data[1]), data[2]),
            )
            self.connection.commit()

            for i in inputs:
                i.clear()

            self.populate_dish_auto_completion()
            self.generate_reports()
            self.generate_menu_table()

            QMessageBox.information(self, "Успех", "Блюдо успешно добавлено.")
        except Exception as e:
            QMessageBox.warning(
                self, "Ошибка", f"Ошибка при добавлении блюда: {str(e)}"
            )

    def add_order(self):
        inputs = [self.table_number_input, self.quantity_input]
        data = [i.text() for i in inputs]

        dish_name, special_requests = (
            self.dish_line_edit.text(),
            self.special_requests_input.text(),
        )

        if not all(data) or not dish_name:
            QMessageBox.warning(
                self, "Ошибка", "Заполните все поля перед добавлением заказа."
            )
            return

        try:
            self.cursor.execute(
                "SELECT dish_id FROM Menu WHERE dish_name = ?", (dish_name,)
            )
            result = self.cursor.fetchone()
            if result:
                dish_id = result[0]
            else:
                QMessageBox.warning(
                    self, "Ошибка", "Выбранное блюдо не найдено в меню."
                )
                return

            try:
                quantity = int(data[1])
                if quantity < 0:
                    raise ValueError(
                        "Количество должно быть неотрицательным целым числом."
                    )
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Ошибка ввода",
                    "Недопустимое значение Количество. Введите неотрицательное целое число.",
                )
                self.quantity_input.clear()
                return

            self.cursor.execute(
                "INSERT INTO Orders (table_number, dish_id, quantity, special_requests) VALUES (?, ?, ?, ?)",
                (str(data[0]), dish_id, str(quantity), special_requests),
            )
            self.connection.commit()

            for i in inputs:
                i.clear()
            self.special_requests_input.clear()
            self.generate_reports()

            QMessageBox.information(self, "Успех", "Заказ успешно добавлен.")
        except Exception as e:
            QMessageBox.warning(
                self, "Ошибка", f"Ошибка при добавлении заказа: {str(e)}"
            )

    def auto_resize_columns(self, table):
        header = table.horizontalHeader()
        for column in range(table.columnCount()):
            header.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeToContents)

    def generate_reports(self):
        try:
            self.cursor.execute(
                "SELECT o.order_id, o.table_number, o.dish_id, o.quantity, o.special_requests, m.image_path FROM Orders o JOIN Menu m ON o.dish_id = m.dish_id"
            )
            orders = self.cursor.fetchall()

            self.reports_table.setRowCount(len(orders) if orders else 0)
            self.reports_table.setColumnCount(len(orders[0]) if orders else 6)
            if orders:
                for i, order in enumerate(orders):
                    for j, item in enumerate(order):
                        table_item = QTableWidgetItem()
                        if j == 5:
                            table_item.setText(item)
                            if os.path.isfile(item):
                                pixmap = QPixmap(item).scaledToWidth(50)
                                table_item.setIcon(QIcon(pixmap))
                            else:
                                table_item.setIcon(QIcon())
                        else:
                            table_item.setText(str(item))
                        self.reports_table.setItem(i, j, table_item)

            self.auto_resize_columns(self.reports_table)

            self.reports_table.setHorizontalHeaderLabels(
                [
                    "ID заказа",
                    "Номер столика",
                    "ID блюда",
                    "Количество",
                    "Дополнительные требования",
                    "Изображение блюда",
                ]
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Ошибка", f"Ошибка при создании отчетов: {str(e)}"
            )

    def generate_menu_table(self):
        try:
            self.cursor.execute("SELECT * FROM Menu")
            menu_items = self.cursor.fetchall()

            self.menu_table.setRowCount(len(menu_items) if menu_items else 0)
            self.menu_table.setColumnCount(len(menu_items[0]) if menu_items else 4)
            if menu_items:
                for i, item in enumerate(menu_items):
                    for j, data in enumerate(item):
                        table_item = QTableWidgetItem()
                        table_item.setText(str(data))
                        self.menu_table.setItem(i, j, table_item)
            self.menu_table.setHorizontalHeaderLabels(
                ["ID блюда", "Название блюда", "Цена", "Путь к изображению"]
            )
            self.auto_resize_columns(self.menu_table)
        except Exception as e:
            QMessageBox.warning(
                self, "Ошибка", f"Ошибка при создании таблицы меню: {str(e)}"
            )

    def handle_item_changed(self, item):
        row, col = item.row(), item.column()
        new_value = item.text()
        sender = self.sender()

        if sender == self.reports_table:
            order_id = int(sender.item(row, 0).text())
            columns = {0: "order_id", 2: "dish_id", 3: "quantity"}
            if col in columns:
                self.validate_and_update(row, col, order_id, columns[col], new_value)
            elif col == 4:
                self.cursor.execute(
                    "UPDATE Orders SET special_requests = ? WHERE order_id = ?",
                    (new_value, order_id),
                )
                self.connection.commit()
        elif sender == self.menu_table:
            dish_id = int(sender.item(row, 0).text())
            if col == 1:
                self.cursor.execute(
                    "UPDATE Menu SET dish_name = ? WHERE dish_id = ?",
                    (new_value, dish_id),
                )
                self.connection.commit()
                self.update_dish_auto_completion()
            elif col == 2:
                try:
                    price = float(new_value)
                    if price < 0:
                        raise ValueError("Цена должна быть неотрицательным числом.")
                    self.cursor.execute(
                        "UPDATE Menu SET price = ? WHERE dish_id = ?", (price, dish_id)
                    )
                    self.connection.commit()
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Ошибка ввода",
                        "Недопустимое значение цены. Введите неотрицательное число.",
                    )
            elif col == 3:
                dish_id = int(self.menu_table.item(row, 0).text())

                try:
                    if os.path.isfile(new_value):
                        self.cursor.execute(
                            "UPDATE Menu SET image_path = ? WHERE dish_id = ?",
                            (new_value, dish_id),
                        )
                        self.connection.commit()
                        self.generate_reports()
                    else:
                        QMessageBox.warning(
                            self, "Ошибка", f"Файл изображения не найден: {new_value}"
                        )
                        self.menu_table.blockSignals(True)
                        self.menu_table.item(row, col).setText("")
                        self.menu_table.blockSignals(False)
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "Ошибка",
                        f"Ошибка при обновлении пути изображения: {str(e)}",
                    )

    def validate_and_update(self, row, col, order_id, column_name, new_value):
        try:
            value = int(new_value)
            if value < 0:
                raise ValueError(
                    f"Значение {column_name} должно быть неотрицательным целым числом."
                )
            self.cursor.execute(
                f"UPDATE Orders SET {column_name} = ? WHERE order_id = ?",
                (value, order_id),
            )
            self.connection.commit()
        except ValueError:
            QMessageBox.warning(
                self,
                "Ошибка ввода",
                f"Недопустимое значение {column_name}. Введите неотрицательное целое число.",
            )

            self.reports_table.blockSignals(True)
            self.reports_table.item(row, col).setText("")

            self.reports_table.blockSignals(False)
            self.connection.commit()
            return


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = RestaurantApp()
    sys.exit(app.exec_())
