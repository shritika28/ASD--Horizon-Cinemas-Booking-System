"""
src/gui/chatbot_widget.py
=========================
Rule-based AI Chatbot Help Assistant.
"""

import tkinter as tk
from tkinter import ttk
import datetime
import re

BG = "#0b1220"
BG2 = "#111b2e"
BG_CARD = "#162338"
ACCENT = "#4f8cff"
FG = "#f8fafc"
FG2 = "#a7b4c8"
BORDER = "#26344a"
USER_BG = "#2563eb"
BOT_BG = "#223047"
SUCCESS = "#22c55e"


class ChatbotWidget(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("HCBS Help Assistant")
        self.geometry("350x500")
        self.configure(bg=BG)
        # float on top without blocking main window
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.hide_widget)

        self.patterns = [
            (
                r".*booking.*how.*|.*how.*book.*",
                "To make a booking, select a date and cinema from the main screen, then click the "
                "'Morning', 'Afternoon', or 'Evening' button for the desired film. Choose your seats "
                "and proceed to checkout."
            ),
            (
                r".*cancel.*booking.*|.*booking.*cancel.*",
                "To cancel a booking, use the 'Cancel Booking' button in the top navigation bar. "
                "You will need the Booking Reference ID and the customer's email. Note: a 50% "
                "cancellation fee applies, and you cannot cancel on the day of the showing."
            ),
            (r".*vip.*price.*|.*price.*vip.*|.*explain.*price.*",
             "VIP pricing is calculated as: Base Price (Lower Hall) + 20% uplift for Upper Gallery "
             "+ an additional 20% uplift for VIP seats on top of that."),
            (r".*advance.*book.*|.*book.*advance.*",
             "Advance bookings can be made up to 1 week (7 days) ahead of the current date."),
            (r".*cancel.*rule.*|.*rule.*cancel.*",
             "Cancellation rules: A 50% fee applies to all cancellations. Cancellations are strictly "
             "not permitted on the day of the showing."),
            (r".*generate.*report.*|.*report.*generate.*",
             "To generate reports, go to the 'Admin Dashboard' and select the 'Reports' or 'Monthly "
             "Revenue' tabs. (This is restricted to Admin/Manager roles)."),
            (r".*add.*cinema.*|.*cinema.*add.*",
             "To add a new cinema, go to the 'Manager Dashboard' and use the Cinema Management tools. "
             "(This is restricted to Manager roles only)."),
            (r".*hi.*|.*hello.*|.*hey.*", "Hello! I am the HCBS Help Assistant. How can I help you today?"),
            (r".*bye.*|.*goodbye.*", "Goodbye! Have a great shift."),
        ]

        self._build_ui()
        self._log_interaction("SYSTEM", "Chatbot widget opened")
        self.add_message("Bot", "Hello! I'm your HCBS Help Assistant. How can I help you today?")

    def hide_widget(self):
        self.withdraw()

    def show_widget(self):
        self.deiconify()
        self.lift()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=ACCENT, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="🤖 HCBS Help Assistant", bg=ACCENT, fg=FG, font=("Segoe UI", 12, "bold")).pack()

        # Chat History
        self.chat_canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.chat_canvas.yview)

        self.chat_frame = tk.Frame(self.chat_canvas, bg=BG)
        self.chat_frame.bind(
            "<Configure>",
            lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        )

        # We need to explicitly set the width of the window to allow word wrap
        self.chat_canvas_window = self.chat_canvas.create_window((0, 0), window=self.chat_frame, anchor="nw", width=330)
        self.chat_canvas.configure(yscrollcommand=scrollbar.set)

        # Bind canvas resize to update the frame width
        self.chat_canvas.bind("<Configure>", lambda e: self.chat_canvas.itemconfig(
            self.chat_canvas_window, width=e.width))

        self.chat_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        # Input Area
        input_frame = tk.Frame(self, bg=BG2, pady=10, padx=10)
        input_frame.pack(fill="x", side="bottom")

        self.input_var = tk.StringVar()
        self.entry = tk.Entry(input_frame, textvariable=self.input_var, font=(
            "Segoe UI", 11), bg=BG_CARD, fg=FG, insertbackground=FG, relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self.send_message())

        btn = tk.Button(input_frame, text="Send", bg=SUCCESS, fg=FG, font=("Segoe UI", 10, "bold"),
                        relief="flat", cursor="hand2", command=self.send_message)
        btn.pack(side="right", ipadx=10, ipady=3)

    def send_message(self):
        text = self.input_var.get().strip()
        if not text:
            return

        self.input_var.set("")
        self.add_message("You", text)
        self._log_interaction("USER", text)

        # Determine response
        response = self.get_bot_response(text)

        # Simulate slight delay
        self.after(500, lambda: self._bot_reply(response))

    def _bot_reply(self, response):
        self.add_message("Bot", response)
        self._log_interaction("BOT", response)

    def get_bot_response(self, text):
        text_lower = text.lower()
        for pattern, response in self.patterns:
            if re.match(pattern, text_lower):
                return response
        return "I'm not sure about that — please ask your manager or check the user guide."

    def add_message(self, sender, text):
        msg_frame = tk.Frame(self.chat_frame, bg=BG)
        msg_frame.pack(fill="x", pady=5)

        now = datetime.datetime.now().strftime("%H:%M")

        if sender == "You":
            bg_col = USER_BG
            align = "e"
            pad_x = (50, 10)
            title = f"{now} | You"
        else:
            bg_col = BOT_BG
            align = "w"
            pad_x = (10, 50)
            title = f"Bot | {now}"

        lbl_title = tk.Label(msg_frame, text=title, bg=BG, fg=FG2, font=("Segoe UI", 8))
        lbl_title.pack(anchor=align, padx=pad_x[1] if sender == "You" else pad_x[0])

        msg_lbl = tk.Label(msg_frame, text=text, bg=bg_col, fg=FG, font=(
            "Segoe UI", 10), wraplength=250, justify="left", padx=10, pady=8)
        msg_lbl.pack(anchor=align, padx=pad_x)

        # Auto-scroll
        self.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    def _log_interaction(self, sender, message):
        try:
            with open("chatbot_log.txt", "a", encoding="utf-8") as f:
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{ts}] {sender}: {message}\n")
        except Exception as e:
            print(f"Failed to log chat: {e}")
