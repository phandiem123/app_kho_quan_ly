"""Trang Export / Import dữ liệu."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import database

FONT = "Segoe UI"

CARD_STYLE = """
    QFrame {
        background: white;
        border: 1px solid #e8e8e8;
        border-radius: 10px;
    }
"""
BTN_PRIMARY = """
    QPushButton {
        background: #111;
        color: white;
        border-radius: 6px;
        padding: 6px 16px;
        border: none;
    }
    QPushButton:hover { background: #333; }
"""
BTN_SECONDARY = """
    QPushButton {
        background: white;
        border: 1px solid #ccc;
        border-radius: 6px;
        padding: 6px 14px;
        color: #444;
    }
    QPushButton:hover { background: #f5f5f5; }
"""
BTN_GRAY = """
    QPushButton {
        background: #666;
        color: white;
        border-radius: 6px;
        padding: 6px 14px;
        border: none;
    }
    QPushButton:hover { background: #555; }
"""


class _Card(QFrame):
    def __init__(self, title: str, description: str,
                 primary_label: str, primary_cb,
                 secondary_label: str | None = None, secondary_cb=None,
                 tertiary_label: str | None = None, tertiary_cb=None):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(CARD_STYLE)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(8)

        t = QLabel(title)
        t.setFont(QFont(FONT, 13, QFont.Weight.Bold))
        t.setStyleSheet("color: #111; border: none;")
        v.addWidget(t)

        d = QLabel(description)
        d.setFont(QFont(FONT, 11))
        d.setStyleSheet("color: #666; border: none;")
        d.setWordWrap(True)
        v.addWidget(d)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()

        if tertiary_label and tertiary_cb:
            tb = QPushButton(tertiary_label)
            tb.setFont(QFont(FONT, 11))
            tb.setStyleSheet(BTN_GRAY)
            tb.clicked.connect(tertiary_cb)
            row.addWidget(tb)

        if secondary_label and secondary_cb:
            sb = QPushButton(secondary_label)
            sb.setFont(QFont(FONT, 11))
            sb.setStyleSheet(BTN_SECONDARY)
            sb.clicked.connect(secondary_cb)
            row.addWidget(sb)

        pb = QPushButton(primary_label)
        pb.setFont(QFont(FONT, 11))
        pb.setStyleSheet(BTN_PRIMARY)
        pb.clicked.connect(primary_cb)
        row.addWidget(pb)

        v.addLayout(row)


class ExportImportPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(32, 28, 32, 28)
        v.setSpacing(20)

        title = QLabel("Export / Import Dữ Liệu")
        title.setFont(QFont(FONT, 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #111;")
        v.addWidget(title)

        # ── Xuất dữ liệu ──────────────────────────────────────────────────────
        v.addWidget(_section_header("XUẤT DỮ LIỆU"))

        export_row = QHBoxLayout()
        export_row.setSpacing(16)
        export_row.addWidget(_Card(
            "Tồn Kho",
            "Xuất toàn bộ tồn kho (kho, mặt hàng, mức hao hỏng, số lượng) ra file Excel.",
            "Xuất Excel", self._export_inventory,
        ))
        export_row.addWidget(_Card(
            "Danh Mục Mặt Hàng",
            "Xuất danh sách mặt hàng (mã, tên, đơn vị tính, niên hạn, đơn giá) ra file Excel.",
            "Xuất Excel", self._export_item_types,
        ))
        export_row.addWidget(_Card(
            "Danh Sách Kho / Đơn Vị",
            "Xuất danh sách kho và đơn vị (mã, tên, loại, địa chỉ) ra file Excel.",
            "Xuất Excel", self._export_warehouses,
        ))
        v.addLayout(export_row)

        # ── Nhập dữ liệu ──────────────────────────────────────────────────────
        v.addWidget(_section_header("NHẬP DỮ LIỆU"))

        import_row = QHBoxLayout()
        import_row.setSpacing(16)
        import_row.addWidget(_Card(
            "Danh Mục Mặt Hàng",
            "Nhập danh sách mặt hàng từ file Excel. Mã đã tồn tại sẽ được cập nhật.",
            "Nhập từ Excel", self._import_item_types,
            secondary_label="Tải Mẫu", secondary_cb=self._template_item_types,
            tertiary_label="Xuất Excel", tertiary_cb=self._export_item_types,
        ))
        import_row.addWidget(_Card(
            "Danh Sách Kho / Đơn Vị",
            "Nhập danh sách kho/đơn vị từ file Excel. Mã đã tồn tại sẽ được cập nhật.",
            "Nhập từ Excel", self._import_warehouses,
            secondary_label="Tải Mẫu", secondary_cb=self._template_warehouses,
            tertiary_label="Xuất Excel", tertiary_cb=self._export_warehouses,
        ))
        import_row.addStretch()
        v.addLayout(import_row)

        import_row2 = QHBoxLayout()
        import_row2.setSpacing(16)
        import_row2.addWidget(_Card(
            "Phiếu Nhập Kho",
            "Nhập hàng loạt phiếu nhập kho từ Excel. Mỗi dòng là một mặt hàng trong phiếu.",
            "Nhập từ Excel", self._import_receipts,
            secondary_label="Tải Mẫu", secondary_cb=self._template_receipts,
            tertiary_label="Xuất Excel", tertiary_cb=self._export_receipts,
        ))
        import_row2.addWidget(_Card(
            "Phiếu Xuất Kho",
            "Nhập hàng loạt phiếu xuất kho từ Excel. Mỗi dòng là một mặt hàng trong phiếu.",
            "Nhập từ Excel", self._import_issues,
            secondary_label="Tải Mẫu", secondary_cb=self._template_issues,
            tertiary_label="Xuất Excel", tertiary_cb=self._export_issues,
        ))
        import_row2.addWidget(_Card(
            "Phiếu Luân Chuyển",
            "Nhập hàng loạt phiếu luân chuyển từ Excel. Mỗi dòng là một mặt hàng trong phiếu.",
            "Nhập từ Excel", self._import_transfers,
            secondary_label="Tải Mẫu", secondary_cb=self._template_transfers,
            tertiary_label="Xuất Excel", tertiary_cb=self._export_transfers,
        ))
        v.addLayout(import_row2)

        v.addStretch()

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_inventory(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất Tồn Kho", "ton_kho.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment

            conn = database.get_conn()
            rows = conn.execute("""
                SELECT w.code AS wh_code, w.name AS wh_name, w.type AS wh_type,
                       t.code AS item_code, t.name AS item_name, t.unit_of_measure,
                       i.quality_level, i.quantity,
                       i.received_at_unit_date, i.manufacture_date, i.lot_number,
                       i.is_shared, i.notes
                FROM inventory i
                JOIN warehouses w ON w.id = i.warehouse_id
                JOIN item_types t  ON t.id = i.item_type_id
                WHERE i.quantity > 0
                ORDER BY w.type, w.name, t.name, i.quality_level
            """).fetchall()

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Tồn Kho"

            headers = [
                "Mã Kho", "Tên Kho", "Loại Kho",
                "Mã Hàng", "Tên Hàng", "ĐVT",
                "Mức HH", "Số Lượng",
                "Ngày Nhập ĐV", "Ngày SX", "Số Lô",
                "Dùng Chung", "Ghi Chú",
            ]
            _write_header(ws, headers)

            for r in rows:
                ws.append([
                    r["wh_code"], r["wh_name"],
                    "Kho Tổng" if r["wh_type"] == "TONG" else "Đơn Vị",
                    r["item_code"], r["item_name"], r["unit_of_measure"],
                    r["quality_level"], r["quantity"],
                    r["received_at_unit_date"] or "",
                    r["manufacture_date"] or "",
                    r["lot_number"] or "",
                    "Có" if r["is_shared"] else "",
                    r["notes"] or "",
                ])

            _auto_width(ws)
            wb.save(path)
            QMessageBox.information(self, "Hoàn tất", f"Đã xuất {len(rows)} dòng.\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _export_item_types(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất Danh Mục Mặt Hàng", "danh_muc_hang.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl

            conn = database.get_conn()
            rows = conn.execute(
                "SELECT code, name, unit_of_measure, total_lifespan_months,"
                "       unit_price, notes, is_active"
                " FROM item_types ORDER BY name"
            ).fetchall()

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Mặt Hàng"

            _write_header(ws, [
                "Mã Hàng", "Tên Hàng", "Đơn Vị Tính",
                "Niên Hạn (tháng)", "Đơn Giá", "Ghi Chú", "Trạng Thái",
            ])
            for r in rows:
                ws.append([
                    r["code"], r["name"], r["unit_of_measure"],
                    r["total_lifespan_months"],
                    float(r["unit_price"] or 0),
                    r["notes"] or "",
                    "Hoạt động" if r["is_active"] else "Đã ẩn",
                ])

            _auto_width(ws)
            wb.save(path)
            QMessageBox.information(self, "Hoàn tất", f"Đã xuất {len(rows)} mặt hàng.\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _export_warehouses(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất Danh Sách Kho", "danh_sach_kho.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl

            conn = database.get_conn()
            rows = conn.execute(
                "SELECT code, name, type, address, notes, is_active"
                " FROM warehouses ORDER BY type, name"
            ).fetchall()

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Kho"

            _write_header(ws, [
                "Mã Kho", "Tên Kho", "Loại (TONG/DON_VI)",
                "Địa Chỉ", "Ghi Chú", "Trạng Thái",
            ])
            for r in rows:
                ws.append([
                    r["code"], r["name"], r["type"],
                    r["address"] or "", r["notes"] or "",
                    "Hoạt động" if r["is_active"] else "Đã ẩn",
                ])

            _auto_width(ws)
            wb.save(path)
            QMessageBox.information(self, "Hoàn tất", f"Đã xuất {len(rows)} kho/đơn vị.\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _export_receipts(self):
        self._export_transactions("NHAP_KHO", "Xuất Phiếu Nhập Kho", "phieu_nhap_kho.xlsx", "Nhập Kho")

    def _export_issues(self):
        self._export_transactions("XUAT_KHO", "Xuất Phiếu Xuất Kho", "phieu_xuat_kho.xlsx", "Xuất Kho")

    def _export_transfers(self):
        self._export_transactions(
            ("LUAN_CHUYEN_KHO", "LUAN_CHUYEN_DV"),
            "Xuất Phiếu Luân Chuyển", "phieu_luan_chuyen.xlsx", "Luân Chuyển",
        )

    def _export_transactions(self, tx_type, dialog_title: str, default_name: str, sheet_name: str):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getSaveFileName(self, dialog_title, default_name, "Excel (*.xlsx)")
        if not path:
            return
        try:
            import openpyxl

            conn = database.get_conn()
            if isinstance(tx_type, tuple):
                placeholders = ",".join("?" * len(tx_type))
                sql = f"""
                    SELECT tx.reference_number, tx.transaction_date, tx.created_by, tx.notes AS tx_notes,
                           wf.code AS from_code, wf.name AS from_name,
                           wt.code AS to_code,   wt.name AS to_name,
                           t.code AS item_code,  t.name AS item_name, t.unit_of_measure,
                           tl.quality_level_from, tl.quality_level_to, tl.quantity,
                           tl.lot_number, tl.notes AS line_notes
                    FROM transactions tx
                    JOIN transaction_lines tl ON tl.transaction_id = tx.id
                    JOIN item_types t  ON t.id  = tl.item_type_id
                    LEFT JOIN warehouses wf ON wf.id = tx.from_warehouse_id
                    LEFT JOIN warehouses wt ON wt.id = tx.to_warehouse_id
                    WHERE tx.type IN ({placeholders})
                    ORDER BY tx.transaction_date DESC, tx.id, tl.id
                """
                rows = conn.execute(sql, tx_type).fetchall()
            else:
                rows = conn.execute("""
                    SELECT tx.reference_number, tx.transaction_date, tx.created_by, tx.notes AS tx_notes,
                           wf.code AS from_code, wf.name AS from_name,
                           wt.code AS to_code,   wt.name AS to_name,
                           t.code AS item_code,  t.name AS item_name, t.unit_of_measure,
                           tl.quality_level_from, tl.quality_level_to, tl.quantity,
                           tl.lot_number, tl.notes AS line_notes
                    FROM transactions tx
                    JOIN transaction_lines tl ON tl.transaction_id = tx.id
                    JOIN item_types t  ON t.id  = tl.item_type_id
                    LEFT JOIN warehouses wf ON wf.id = tx.from_warehouse_id
                    LEFT JOIN warehouses wt ON wt.id = tx.to_warehouse_id
                    WHERE tx.type = ?
                    ORDER BY tx.transaction_date DESC, tx.id, tl.id
                """, (tx_type,)).fetchall()

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = sheet_name

            _write_header(ws, [
                "Số Phiếu", "Ngày", "Người Lập", "Ghi Chú Phiếu",
                "Mã Kho Từ", "Tên Kho Từ", "Mã Kho Đến", "Tên Kho Đến",
                "Mã Hàng", "Tên Hàng", "ĐVT",
                "Mức HH Từ", "Mức HH Đến", "Số Lượng",
                "Số Lô", "Ghi Chú Dòng",
            ])
            for r in rows:
                ws.append([
                    r["reference_number"] or "",
                    r["transaction_date"] or "",
                    r["created_by"] or "",
                    r["tx_notes"] or "",
                    r["from_code"] or "", r["from_name"] or "",
                    r["to_code"] or "",   r["to_name"] or "",
                    r["item_code"], r["item_name"], r["unit_of_measure"],
                    r["quality_level_from"] or "",
                    r["quality_level_to"],
                    r["quantity"],
                    r["lot_number"] or "",
                    r["line_notes"] or "",
                ])

            _auto_width(ws)
            wb.save(path)
            QMessageBox.information(self, "Hoàn tất", f"Đã xuất {len(rows)} dòng.\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    # ── Import ────────────────────────────────────────────────────────────────

    def _import_item_types(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn File Excel", "", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path)
            ws = wb.active
            rows = list(ws.iter_rows(min_row=2, values_only=True))

            conn = database.get_conn()
            inserted = updated = skipped = 0
            errors = []

            for i, row in enumerate(rows, start=2):
                if not row or not row[0]:
                    continue
                try:
                    code = str(row[0]).strip()
                    name = str(row[1]).strip() if row[1] else ""
                    uom  = str(row[2]).strip() if row[2] else ""
                    life = int(row[3]) if row[3] else 0
                    price = float(row[4]) if row[4] else 0.0
                    notes = str(row[5]).strip() if len(row) > 5 and row[5] else ""

                    if not code or not name or not uom or not life:
                        errors.append(f"Dòng {i}: thiếu dữ liệu bắt buộc")
                        skipped += 1
                        continue

                    existing = conn.execute(
                        "SELECT id FROM item_types WHERE code=?", (code,)
                    ).fetchone()

                    if existing:
                        conn.execute(
                            "UPDATE item_types SET name=?, unit_of_measure=?,"
                            " total_lifespan_months=?, unit_price=?, notes=? WHERE code=?",
                            (name, uom, life, price, notes, code),
                        )
                        updated += 1
                    else:
                        conn.execute(
                            "INSERT INTO item_types (code, name, unit_of_measure,"
                            " total_lifespan_months, unit_price, notes)"
                            " VALUES (?,?,?,?,?,?)",
                            (code, name, uom, life, price, notes),
                        )
                        inserted += 1
                except Exception as row_err:
                    errors.append(f"Dòng {i}: {row_err}")
                    skipped += 1

            conn.commit()

            msg = f"Thêm mới: {inserted}   Cập nhật: {updated}   Bỏ qua: {skipped}"
            if errors:
                msg += "\n\nChi tiết lỗi:\n" + "\n".join(errors[:10])
            QMessageBox.information(self, "Nhập hoàn tất", msg)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _import_warehouses(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn File Excel", "", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path)
            ws = wb.active
            rows = list(ws.iter_rows(min_row=2, values_only=True))

            conn = database.get_conn()
            inserted = updated = skipped = 0
            errors = []
            VALID_TYPES = {"TONG", "DON_VI"}

            for i, row in enumerate(rows, start=2):
                if not row or not row[0]:
                    continue
                try:
                    code    = str(row[0]).strip()
                    name    = str(row[1]).strip() if row[1] else ""
                    wh_type = str(row[2]).strip().upper() if row[2] else ""
                    address = str(row[3]).strip() if len(row) > 3 and row[3] else ""
                    notes   = str(row[4]).strip() if len(row) > 4 and row[4] else ""

                    if not code or not name or wh_type not in VALID_TYPES:
                        errors.append(
                            f"Dòng {i}: thiếu hoặc sai dữ liệu "
                            f"(Loại phải là TONG hoặc DON_VI)"
                        )
                        skipped += 1
                        continue

                    existing = conn.execute(
                        "SELECT id FROM warehouses WHERE code=?", (code,)
                    ).fetchone()

                    if existing:
                        conn.execute(
                            "UPDATE warehouses SET name=?, type=?, address=?, notes=?"
                            " WHERE code=?",
                            (name, wh_type, address, notes, code),
                        )
                        updated += 1
                    else:
                        conn.execute(
                            "INSERT INTO warehouses (code, name, type, address, notes)"
                            " VALUES (?,?,?,?,?)",
                            (code, name, wh_type, address, notes),
                        )
                        inserted += 1
                except Exception as row_err:
                    errors.append(f"Dòng {i}: {row_err}")
                    skipped += 1

            conn.commit()

            msg = f"Thêm mới: {inserted}   Cập nhật: {updated}   Bỏ qua: {skipped}"
            if errors:
                msg += "\n\nChi tiết lỗi:\n" + "\n".join(errors[:10])
            QMessageBox.information(self, "Nhập hoàn tất", msg)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    # ── Download templates ────────────────────────────────────────────────────

    def _template_receipts(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu File Mẫu", "mau_phieu_nhap_kho.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Phiếu Nhập Kho"
            _write_header(ws, [
                "Số Phiếu *", "Ngày * (yyyy-mm-dd)", "Người Lập", "Ghi Chú",
                "Mã Kho Nhận *", "Mã Hàng *", "Số Lượng *", "Ghi Chú Dòng",
            ])
            ws.append(["NK001", "2024-01-15", "Nguyễn Văn A", "", "KHO01", "AK47", 10, ""])
            ws.append(["NK001", "2024-01-15", "Nguyễn Văn A", "", "KHO01", "B40",  5,  ""])
            _auto_width(ws)
            wb.save(path)
            QMessageBox.information(self, "Đã lưu", f"File mẫu:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _template_issues(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu File Mẫu", "mau_phieu_xuat_kho.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Phiếu Xuất Kho"
            _write_header(ws, [
                "Số Phiếu *", "Ngày * (yyyy-mm-dd)", "Người Lập", "Ghi Chú",
                "Mã Kho Từ *", "Mã Đơn Vị Nhận", "Mã Hàng *", "Số Lượng *", "Ghi Chú Dòng",
            ])
            ws.append(["XK001", "2024-01-20", "Trần Thị B", "", "KHO01", "DV01", "AK47", 3, ""])
            ws.append(["XK001", "2024-01-20", "Trần Thị B", "", "KHO01", "DV01", "B40",  2, ""])
            _auto_width(ws)
            wb.save(path)
            QMessageBox.information(self, "Đã lưu", f"File mẫu:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _template_transfers(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu File Mẫu", "mau_phieu_luan_chuyen.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Phiếu Luân Chuyển"
            _write_header(ws, [
                "Số Phiếu *", "Ngày * (yyyy-mm-dd)", "Loại * (TONG/DON_VI)",
                "Người Lập", "Ghi Chú",
                "Mã Kho Từ *", "Mã Kho Đến *",
                "Mã Hàng *", "Mức HH (DON_VI)", "Số Lượng *", "Ghi Chú Dòng",
            ])
            ws.append(["LC001", "2024-02-01", "TONG", "Lê Văn C", "", "KHO01", "KHO02", "AK47", "", 5, ""])
            ws.append(["LC002", "2024-02-05", "DON_VI", "Lê Văn C", "", "DV01", "DV02", "AK47", "H2", 2, ""])
            _auto_width(ws)
            wb.save(path)
            QMessageBox.information(self, "Đã lưu", f"File mẫu:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _import_receipts(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Chọn File Excel", "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            import openpyxl
            from collections import OrderedDict
            from database.receipts import Receipt, ReceiptLine, insert as _insert

            wb = openpyxl.load_workbook(path)
            ws = wb.active
            rows = list(ws.iter_rows(min_row=2, values_only=True))

            conn = database.get_conn()
            wh_map = {r["code"]: r["id"] for r in conn.execute(
                "SELECT code, id FROM warehouses WHERE is_active=1"
            ).fetchall()}
            item_map = {r["code"]: dict(r) for r in conn.execute(
                "SELECT code, id, name, unit_of_measure FROM item_types WHERE is_active=1"
            ).fetchall()}

            groups: OrderedDict = OrderedDict()
            errors: list[str] = []

            for i, row in enumerate(rows, start=2):
                if not row or not row[0]:
                    continue
                so_phieu  = str(row[0]).strip()
                ngay      = str(row[1]).strip() if row[1] else ""
                nguoi_lap = str(row[2]).strip() if row[2] else ""
                ghi_chu   = str(row[3]).strip() if row[3] else ""
                ma_kho    = str(row[4]).strip() if row[4] else ""
                ma_hang   = str(row[5]).strip() if row[5] else ""
                so_luong  = int(row[6]) if row[6] else 0
                ghi_chu_dong = str(row[7]).strip() if len(row) > 7 and row[7] else ""

                if not so_phieu or not ngay or not ma_kho or not ma_hang or not so_luong:
                    errors.append(f"Dòng {i}: thiếu dữ liệu bắt buộc")
                    continue
                if ma_kho not in wh_map:
                    errors.append(f"Dòng {i}: không tìm thấy kho '{ma_kho}'")
                    continue
                if ma_hang not in item_map:
                    errors.append(f"Dòng {i}: không tìm thấy mặt hàng '{ma_hang}'")
                    continue

                key = (so_phieu, ngay, nguoi_lap, ghi_chu, ma_kho)
                if key not in groups:
                    groups[key] = dict(so_phieu=so_phieu, ngay=ngay, nguoi_lap=nguoi_lap,
                                       ghi_chu=ghi_chu, wh_id=wh_map[ma_kho], lines=[])
                it = item_map[ma_hang]
                groups[key]["lines"].append(ReceiptLine(
                    item_type_id=it["id"], item_code=it["code"],
                    item_name=it["name"], unit_of_measure=it["unit_of_measure"],
                    quantity=so_luong, notes=ghi_chu_dong,
                ))

            inserted = 0
            for g in groups.values():
                _insert(Receipt(
                    id=None, reference_number=g["so_phieu"],
                    to_warehouse_id=g["wh_id"], to_warehouse_name="",
                    transaction_date=g["ngay"], created_by=g["nguoi_lap"],
                    notes=g["ghi_chu"], lines=g["lines"],
                ))
                inserted += 1

            msg = f"Đã tạo {inserted} phiếu nhập kho."
            if errors:
                msg += f"\n\nBỏ qua {len(errors)} dòng lỗi:\n" + "\n".join(errors[:10])
            QMessageBox.information(self, "Nhập hoàn tất", msg)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _import_issues(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Chọn File Excel", "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            import openpyxl
            from collections import OrderedDict
            from database.xuat_kho import Issue, IssueLine, insert as _insert

            wb = openpyxl.load_workbook(path)
            ws = wb.active
            rows = list(ws.iter_rows(min_row=2, values_only=True))

            conn = database.get_conn()
            wh_map = {r["code"]: r["id"] for r in conn.execute(
                "SELECT code, id FROM warehouses WHERE is_active=1"
            ).fetchall()}
            item_map = {r["code"]: dict(r) for r in conn.execute(
                "SELECT code, id, name, unit_of_measure FROM item_types WHERE is_active=1"
            ).fetchall()}

            groups: OrderedDict = OrderedDict()
            errors: list[str] = []

            for i, row in enumerate(rows, start=2):
                if not row or not row[0]:
                    continue
                so_phieu  = str(row[0]).strip()
                ngay      = str(row[1]).strip() if row[1] else ""
                nguoi_lap = str(row[2]).strip() if row[2] else ""
                ghi_chu   = str(row[3]).strip() if row[3] else ""
                ma_kho_tu = str(row[4]).strip() if row[4] else ""
                ma_kho_den= str(row[5]).strip() if row[5] else ""
                ma_hang   = str(row[6]).strip() if row[6] else ""
                so_luong  = int(row[7]) if row[7] else 0
                ghi_chu_dong = str(row[8]).strip() if len(row) > 8 and row[8] else ""

                if not so_phieu or not ngay or not ma_kho_tu or not ma_hang or not so_luong:
                    errors.append(f"Dòng {i}: thiếu dữ liệu bắt buộc")
                    continue
                if ma_kho_tu not in wh_map:
                    errors.append(f"Dòng {i}: không tìm thấy kho '{ma_kho_tu}'")
                    continue
                if ma_hang not in item_map:
                    errors.append(f"Dòng {i}: không tìm thấy mặt hàng '{ma_hang}'")
                    continue
                to_id = wh_map.get(ma_kho_den) if ma_kho_den else None

                key = (so_phieu, ngay, nguoi_lap, ghi_chu, ma_kho_tu, ma_kho_den)
                if key not in groups:
                    groups[key] = dict(
                        so_phieu=so_phieu, ngay=ngay, nguoi_lap=nguoi_lap,
                        ghi_chu=ghi_chu, from_id=wh_map[ma_kho_tu], to_id=to_id,
                        lines=[],
                    )
                it = item_map[ma_hang]
                groups[key]["lines"].append(IssueLine(
                    item_type_id=it["id"], item_code=it["code"],
                    item_name=it["name"], unit_of_measure=it["unit_of_measure"],
                    quantity=so_luong, notes=ghi_chu_dong,
                ))

            inserted = 0
            for g in groups.values():
                _insert(Issue(
                    id=None, reference_number=g["so_phieu"],
                    from_warehouse_id=g["from_id"], from_warehouse_name="",
                    to_warehouse_id=g["to_id"], to_warehouse_name="",
                    transaction_date=g["ngay"], created_by=g["nguoi_lap"],
                    notes=g["ghi_chu"], lines=g["lines"],
                ))
                inserted += 1

            msg = f"Đã tạo {inserted} phiếu xuất kho."
            if errors:
                msg += f"\n\nBỏ qua {len(errors)} dòng lỗi:\n" + "\n".join(errors[:10])
            QMessageBox.information(self, "Nhập hoàn tất", msg)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _import_transfers(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Chọn File Excel", "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            import openpyxl
            from collections import OrderedDict
            from database.luan_chuyen import Transfer, TransferLine, insert as _insert

            wb = openpyxl.load_workbook(path)
            ws = wb.active
            rows = list(ws.iter_rows(min_row=2, values_only=True))

            conn = database.get_conn()
            wh_map = {r["code"]: r["id"] for r in conn.execute(
                "SELECT code, id FROM warehouses WHERE is_active=1"
            ).fetchall()}
            item_map = {r["code"]: dict(r) for r in conn.execute(
                "SELECT code, id, name, unit_of_measure FROM item_types WHERE is_active=1"
            ).fetchall()}

            groups: OrderedDict = OrderedDict()
            errors: list[str] = []
            VALID_TYPES = {"TONG", "DON_VI"}

            for i, row in enumerate(rows, start=2):
                if not row or not row[0]:
                    continue
                so_phieu  = str(row[0]).strip()
                ngay      = str(row[1]).strip() if row[1] else ""
                loai      = str(row[2]).strip().upper() if row[2] else ""
                nguoi_lap = str(row[3]).strip() if row[3] else ""
                ghi_chu   = str(row[4]).strip() if row[4] else ""
                ma_tu     = str(row[5]).strip() if row[5] else ""
                ma_den    = str(row[6]).strip() if row[6] else ""
                ma_hang   = str(row[7]).strip() if row[7] else ""
                muc_hh    = str(row[8]).strip().upper() if row[8] else "H1"
                so_luong  = int(row[9]) if row[9] else 0
                ghi_chu_dong = str(row[10]).strip() if len(row) > 10 and row[10] else ""

                if not so_phieu or not ngay or loai not in VALID_TYPES \
                        or not ma_tu or not ma_den or not ma_hang or not so_luong:
                    errors.append(f"Dòng {i}: thiếu hoặc sai dữ liệu bắt buộc")
                    continue
                if ma_tu not in wh_map:
                    errors.append(f"Dòng {i}: không tìm thấy kho '{ma_tu}'")
                    continue
                if ma_den not in wh_map:
                    errors.append(f"Dòng {i}: không tìm thấy kho '{ma_den}'")
                    continue
                if ma_hang not in item_map:
                    errors.append(f"Dòng {i}: không tìm thấy mặt hàng '{ma_hang}'")
                    continue
                if muc_hh not in ("H1", "H2", "H3", "H4"):
                    muc_hh = "H1"

                tx_type = "LUAN_CHUYEN_KHO" if loai == "TONG" else "LUAN_CHUYEN_DV"
                key = (so_phieu, ngay, tx_type, nguoi_lap, ghi_chu, ma_tu, ma_den)
                if key not in groups:
                    groups[key] = dict(
                        so_phieu=so_phieu, ngay=ngay, tx_type=tx_type,
                        nguoi_lap=nguoi_lap, ghi_chu=ghi_chu,
                        from_id=wh_map[ma_tu], to_id=wh_map[ma_den],
                        lines=[],
                    )
                it = item_map[ma_hang]
                groups[key]["lines"].append(TransferLine(
                    item_type_id=it["id"], item_code=it["code"],
                    item_name=it["name"], unit_of_measure=it["unit_of_measure"],
                    quantity=so_luong, quality_level=muc_hh, notes=ghi_chu_dong,
                ))

            inserted = 0
            for g in groups.values():
                _insert(Transfer(
                    id=None, reference_number=g["so_phieu"],
                    from_warehouse_id=g["from_id"], from_warehouse_name="",
                    to_warehouse_id=g["to_id"], to_warehouse_name="",
                    transaction_date=g["ngay"], tx_type=g["tx_type"],
                    created_by=g["nguoi_lap"], notes=g["ghi_chu"],
                    lines=g["lines"],
                ))
                inserted += 1

            msg = f"Đã tạo {inserted} phiếu luân chuyển."
            if errors:
                msg += f"\n\nBỏ qua {len(errors)} dòng lỗi:\n" + "\n".join(errors[:10])
            QMessageBox.information(self, "Nhập hoàn tất", msg)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _template_item_types(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu File Mẫu", "mau_mat_hang.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Mặt Hàng"
            _write_header(ws, [
                "Mã Hàng *", "Tên Hàng *", "Đơn Vị Tính *",
                "Niên Hạn (tháng) *", "Đơn Giá", "Ghi Chú",
            ])
            ws.append(["AK47", "Súng AK47", "cái", 120, 15000000, ""])
            _auto_width(ws)
            wb.save(path)
            QMessageBox.information(self, "Đã lưu", f"File mẫu:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _template_warehouses(self):
        if not _check_openpyxl(self):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu File Mẫu", "mau_kho.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Kho"
            _write_header(ws, [
                "Mã Kho *", "Tên Kho *", "Loại (TONG/DON_VI) *",
                "Địa Chỉ", "Ghi Chú",
            ])
            ws.append(["D6", "Kho Tổng D6", "TONG", "123 Đường ABC", ""])
            ws.append(["DV01", "Đơn Vị 01", "DON_VI", "456 Đường XYZ", ""])
            _auto_width(ws)
            wb.save(path)
            QMessageBox.information(self, "Đã lưu", f"File mẫu:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _section_header(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont(FONT, 10, QFont.Weight.Bold))
    lbl.setStyleSheet("color: #999;")
    return lbl


def _check_openpyxl(parent: QWidget) -> bool:
    try:
        import openpyxl  # noqa: F401
        return True
    except ImportError:
        QMessageBox.warning(
            parent, "Thiếu thư viện",
            "Vui lòng cài đặt:\n\npip install openpyxl"
        )
        return False


def _write_header(ws, headers: list[str]):
    from openpyxl.styles import Font, PatternFill, Alignment
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, name="Calibri")
        cell.fill = PatternFill(fill_type="solid", fgColor="111111")
        cell.font = Font(bold=True, color="FFFFFF", name="Calibri")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 20


def _auto_width(ws):
    for col in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)
