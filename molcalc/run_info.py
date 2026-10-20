# --- Info Window (live-updating) ---
def open_info_window(clear=False):
    """Open the Run Info window. If clear=True, wipe existing content first."""
    global info_log, info_window, info_text_widget
    from tkinter.scrolledtext import ScrolledText

    if info_window and info_window.winfo_exists():
        # Window already open — optionally clear for a fresh run
        if clear and info_text_widget:
            info_text_widget.config(state='normal')
            info_text_widget.delete('1.0', 'end')
            info_text_widget.config(state='normal')  # keep editable for live writes
        info_window.lift()
        return

    info_window = tk.Toplevel(window)
    info_window.title('Run Info')
    info_window.geometry('820x560')
    info_window.resizable(True, True)
    st = ScrolledText(info_window, wrap='word', font=('Courier New', 9),
                      bg='#1e1e1e', fg='#d4d4d4', insertbackground='white')
    st.pack(fill='both', expand=True, padx=6, pady=6)
    info_text_widget = st

def _log_live(text):
    """Append a line to info_log, print it, and push live to the info window."""
    line = str(text)
    info_log.append(line)
    print(line)
    if info_text_widget and info_window and info_window.winfo_exists():
        try:
            info_text_widget.config(state='normal')
            info_text_widget.insert('end', line + '\n')
            info_text_widget.see('end')
            info_text_widget.update_idletasks()
        except Exception:
            pass
