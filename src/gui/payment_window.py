import tkinter as tk
from tkinter import ttk
import datetime
import re

BG = "#0b1220"
BG2 = "#111b2e"
ACCENT = "#4f8cff"
FG = "#f8fafc"
TEXT2 = "#a7b4c8"
SUCCESS = "#22c55e"
ERROR = "#ef4444"


class PaymentWindow:
    def __init__(self, root: tk.Toplevel, total_amount: float, booking_data: dict, on_payment_success: callable):
        self.root = tk.Toplevel(root)
        self.root.title("Secure Payment Gateway")
        self.root.geometry("450x550")
        self.root.configure(bg=BG)
        self.root.grab_set()
        self.root.focus_force()

        self.total_amount = total_amount
        self.booking_data = booking_data
        self.on_payment_success = on_payment_success

        self._build_ui()

    def _build_ui(self):
        title_lbl = tk.Label(self.root, text="💳 Secure Payment", font=("Segoe UI", 18, "bold"), bg=BG, fg=FG)
        title_lbl.pack(pady=(30, 10))

        amt_lbl = tk.Label(self.root, text=f"Total Amount to Charge: £{self.total_amount:.2f}", font=(
            "Segoe UI", 14), bg=BG, fg=SUCCESS)
        amt_lbl.pack(pady=(0, 20))

        form_frame = tk.Frame(self.root, bg=BG)
        form_frame.pack(fill="both", expand=True, padx=40)

        # Name
        tk.Label(form_frame, text="Cardholder Name", bg=BG, fg=TEXT2, font=(
            "Segoe UI", 10)).grid(row=0, column=0, sticky="w", pady=(10, 0))
        self.name_ent = tk.Entry(form_frame, width=35, font=("Segoe UI", 12), bg=BG, fg=FG,
                                 insertbackground=FG, relief="flat",
                                 highlightbackground="#E2E8F0", highlightthickness=1)
        self.name_ent.grid(row=1, column=0, sticky="we", pady=(5, 0), ipady=5)
        self.name_err = tk.Label(form_frame, text="", bg=BG, fg=ERROR, font=("Segoe UI", 9))
        self.name_err.grid(row=2, column=0, sticky="w")

        # Card Number
        tk.Label(form_frame, text="Card Number", bg=BG, fg=TEXT2, font=(
            "Segoe UI", 10)).grid(row=3, column=0, sticky="w", pady=(5, 0))

        self.card_var = tk.StringVar()
        self.card_var.trace_add('write', self._format_card_number)

        self.card_ent = tk.Entry(form_frame, textvariable=self.card_var, width=35, font=(
            "Segoe UI", 12), bg=BG, fg=FG, insertbackground=FG, relief="flat",
            highlightbackground="#E2E8F0", highlightthickness=1)
        self.card_ent.grid(row=4, column=0, sticky="we", pady=(5, 0), ipady=5)
        self.card_err = tk.Label(form_frame, text="", bg=BG, fg=ERROR, font=("Segoe UI", 9))
        self.card_err.grid(row=5, column=0, sticky="w")

        # Expiry and CVV frame
        row_frame = tk.Frame(form_frame, bg=BG)
        row_frame.grid(row=6, column=0, sticky="we", pady=(5, 0))
        row_frame.columnconfigure(0, weight=1)
        row_frame.columnconfigure(1, weight=1)

        # Expiry
        tk.Label(row_frame, text="Expiry (MM/YY)", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        self.exp_ent = tk.Entry(row_frame, width=14, font=("Segoe UI", 12), bg=BG, fg=FG,
                                insertbackground=FG, relief="flat", highlightbackground="#E2E8F0", highlightthickness=1)
        self.exp_ent.grid(row=1, column=0, sticky="w", pady=(5, 0), ipady=5)
        self.exp_err = tk.Label(row_frame, text="", bg=BG, fg=ERROR, font=("Segoe UI", 9))
        self.exp_err.grid(row=2, column=0, sticky="w")

        # CVV
        tk.Label(row_frame, text="CVV", bg=BG, fg=TEXT2, font=("Segoe UI", 10)).grid(row=0, column=1, sticky="w")
        self.cvv_ent = tk.Entry(row_frame, width=8, font=("Segoe UI", 12), bg=BG, fg=FG,
                                insertbackground=FG, relief="flat", highlightbackground="#E2E8F0", highlightthickness=1)
        self.cvv_ent.grid(row=1, column=1, sticky="w", pady=(5, 0), ipady=5)
        self.cvv_err = tk.Label(row_frame, text="", bg=BG, fg=ERROR, font=("Segoe UI", 9))
        self.cvv_err.grid(row=2, column=1, sticky="w")

        # Action Frame
        self.act_frame = tk.Frame(self.root, bg=BG)
        self.act_frame.pack(fill="x", side="bottom", pady=30, padx=40)

        tk.Button(self.act_frame, text="Cancel", font=("Segoe UI", 11, "bold"), bg=BG2, fg=FG, relief="flat",
                  padx=20, pady=8, command=self.root.destroy, cursor="hand2").pack(side="left")

        self.pay_btn = tk.Button(self.act_frame, text="Pay Now", font=("Segoe UI", 11, "bold"), bg=SUCCESS,
                                 fg="#FFFFFF", relief="flat", padx=20, pady=8, command=self._submit, cursor="hand2")
        self.pay_btn.pack(side="right")

        # Progress/Status frame
        self.prog_frame = tk.Frame(self.root, bg=BG)
        self.prog_lbl = tk.Label(self.prog_frame, text="", bg=BG, fg=FG, font=("Segoe UI", 12, "bold"))
        self.prog_lbl.pack(pady=(0, 15))

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("green.Horizontal.TProgressbar", background=SUCCESS)

        self.progress = ttk.Progressbar(self.prog_frame, orient="horizontal",
                                        mode="indeterminate", length=300, style="green.Horizontal.TProgressbar")

    def _format_card_number(self, *args):
        val = self.card_var.get().replace(" ", "")
        if not val.isdigit() and len(val) > 0:
            val = ''.join(filter(str.isdigit, val))

        if len(val) > 16:
            val = val[:16]

        formatted = " ".join([val[i:i + 4] for i in range(0, len(val), 4)])

        if formatted != self.card_var.get():
            self.card_var.set(formatted)
            self.card_ent.icursor("end")

    def _clear_errors(self):
        self.name_err.config(text="")
        self.card_err.config(text="")
        self.exp_err.config(text="")
        self.cvv_err.config(text="")

    def _submit(self):
        self._clear_errors()
        valid = True

        name = self.name_ent.get().strip()
        if not name:
            self.name_err.config(text="Cardholder name is required")
            valid = False

        card = self.card_var.get().replace(" ", "")
        if len(card) != 16 or not card.isdigit():
            self.card_err.config(text="Card number must be exactly 16 digits")
            valid = False

        exp = self.exp_ent.get().strip()
        if not re.match(r"^(0[1-9]|1[0-2])\/\d{2}$", exp):
            self.exp_err.config(text="Format must be MM/YY")
            valid = False
        else:
            try:
                m, y = map(int, exp.split('/'))
                y += 2000
                today = datetime.date.today()

                # Check if expired (must be valid future or current month)
                if y < today.year or (y == today.year and m < today.month):
                    self.exp_err.config(text="Card has expired")
                    valid = False
            except Exception:
                self.exp_err.config(text="Invalid date")
                valid = False

        cvv = self.cvv_ent.get().strip()
        if len(cvv) != 3 or not cvv.isdigit():
            self.cvv_err.config(text="CVV must be 3 digits")
            valid = False

        if not valid:
            return

        self._simulate_processing()

    def _simulate_processing(self):
        self.act_frame.pack_forget()
        self.prog_frame.pack(fill="x", side="bottom", pady=30, padx=40)
        self.progress.pack()
        self.prog_lbl.config(text="Processing Payment...", fg=TEXT2)

        # Disable inputs
        self.name_ent.config(state="disabled")
        self.card_ent.config(state="disabled")
        self.exp_ent.config(state="disabled")
        self.cvv_ent.config(state="disabled")

        self.progress.start(15)

        self.root.after(2000, self._on_processing_complete)

    def _on_processing_complete(self):
        self.progress.stop()
        self.progress.pack_forget()
        self.prog_lbl.config(text="Payment Successful!", fg=SUCCESS, font=("Segoe UI", 14, "bold"))

        # Give user a moment to see success before closing
        self.root.after(1000, self._finalize)

    def _finalize(self):
        self.root.destroy()
        self.on_payment_success(self.booking_data)


if __name__ == "__main__":
    r = tk.Tk()
    r.withdraw()
    PaymentWindow(r, 24.50, {"ref": "123"}, lambda d: print("Success!", d))
    r.mainloop()
