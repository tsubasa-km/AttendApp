from datetime import datetime, timedelta
from pystray import MenuItem as item
from bs4 import BeautifulSoup
from win11toast import toast
from typing import Callable
from PIL import Image
import flet as ft
import threading
import requests
import pystray
import pickle
import time
import sys
import os
import re


LOGIN_URL = "https://www5.clipperportal.net/a1fedb/smt/a0101.php"
ATTEND_URL = "https://www5.clipperportal.net/a1fedb/smt/h0201.php"

DATAFILE_PATH = "./data.pickle"

session: requests.Session
soup: BeautifulSoup

user_id: str
user_pw: str


def login() -> bool:
    global session, soup
    session = requests.Session()
    session.post(url=LOGIN_URL, data={"UserId": user_id, "Password": user_pw})
    res = session.get(ATTEND_URL)
    soup = BeautifulSoup(res.content, "html.parser")
    return res.url != LOGIN_URL


def attend() -> bool:
    if not login():
        raise Exception("ログインに失敗しました。")
    auth_raws = soup.findAll(onclick=re.compile("js_AuthGeolocationData"))
    if len(auth_raws) == 0 or auth_raws[0].has_attr('disabled'):
        return False
    auth_data_list = re.findall("'(.*?)'", auth_raws[0]["onclick"])
    data = {
        "lat": "35.46391397024158",
        "lng": "139.51350417569222",
        "error": "",
        "setPeriod": auth_data_list[0],
        "setFramejudgment": auth_data_list[1],
        "setBeginTime": auth_data_list[2],
        "setLessonId": auth_data_list[3],
        "setAttendanceType": auth_data_list[4]}
    session.post(f"{ATTEND_URL}?action=auth", data=data)
    session.get(ATTEND_URL)
    session.post(
        f"{ATTEND_URL}?action=update")
    res = session.get(ATTEND_URL)
    return res.ok


def data_save(data):
    with open(DATAFILE_PATH, mode="wb") as f:
        pickle.dump(data, f)


def data_load():
    if not os.path.exists(DATAFILE_PATH):
        data_save({"user_id": "", "user_pw": ""})
    with open(DATAFILE_PATH, mode="br") as f:
        d = pickle.load(f)
    return d


def register(page: ft.Page):
    global user_id, user_pw
    page.window_center()
    page.window_width = 600
    page.window_height = 600
    user_id_field = ft.TextField(label="ID", width=300, value=user_id)
    user_pw_field = ft.TextField(label="Password", password=True,
                                 can_reveal_password=True, width=300, value=user_pw)
    result = ft.Text()

    def login_verify(e):
        global user_id, user_pw
        user_id = user_id_field.value
        user_pw = user_pw_field.value
        if login():
            result.value = "ログインできました。"
            result.color = ft.colors.BLUE_400
        else:
            result.value = "IDかPasswordが違います。"
            result.color = ft.colors.RED_400
        page.update()

    def save(e):
        data_save({
            "user_id": user_id_field.value,
            "user_pw": user_pw_field.value})
        result.value = "保存しました。"
        result.color = ft.colors.BLUE_400
        page.update()

    verify_button = ft.ElevatedButton(text="ログインチェック", on_click=login_verify)
    save_button = ft.ElevatedButton(
        text="保存", on_click=save, style=ft.ButtonStyle(bgcolor=ft.colors.BLUE_200))

    login_card = ft.Container(
        content=ft.Column(
            [
                ft.Text("自動出席登録", size=30, weight="bold"),
                ft.Text("ログイン情報登録", size=20),
                user_id_field,
                user_pw_field,
                ft.Row([verify_button, save_button],
                       alignment=ft.MainAxisAlignment.CENTER),
                result,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=20,
        border_radius=10,
        width=400,
        height=350,
        alignment=ft.alignment.center,
        bgcolor="white",
        shadow=ft.BoxShadow(
            spread_radius=2,
            blur_radius=15,
            color="grey",
            offset=ft.Offset(0, 5)
        )
    )

    page.add(
        ft.Container(
            content=login_card,
            alignment=ft.alignment.center,
            expand=True
        )
    )


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def deamon(task):
    def on_quit(icon, item):
        icon.stop()
        sys.exit()
    icon_image = Image.open(resource_path("icon.ico"))
    icon = pystray.Icon("test_icon")
    icon.icon = icon_image
    icon.menu = pystray.Menu(item('Quit', on_quit),
                             item('Register', lambda: ft.app(register)))
    thread = threading.Thread(target=task)
    thread.daemon = True
    thread.start()

    # Run the icon
    icon.run()


def schedule_job(time_list: list[int, datetime], time_limit_min: float, func: Callable[[int,], None]):
    time_list = list(filter(lambda t: datetime.now() < t[1], time_list))
    try:
        for t in time_list:
            start = t[1]-timedelta(minutes=time_limit_min)
            while True:
                if start < datetime.now() < t[1]:
                    func(t[0])
                    break
                sleep_time = start-datetime.now()
                time.sleep(sleep_time.seconds + 30)
    except KeyboardInterrupt:
        return


def main():
    def job(n):
        if attend():
            toast("AttendApp", f"{n}時間目 出席登録しました。")
        else:
            toast("AttendApp", f"{n}時間目 出席登録に失敗しました。")

    global user_id, user_pw

    user_id, user_pw = data_load().values()
    time_list = ["09:00", "09:50", "10:45",
                 "11:35", "13:05", "13:55", "14:50", "15:40"]
    today_str = datetime.today().date().strftime(r"%Y-%m-%d")
    time_list = [datetime.strptime(
        f"{today_str} {t}", r"%Y-%m-%d %H:%M") for t in time_list]
    time_list = list(zip(range(1, 9), time_list))
    if not login():
        ft.app(register)
    deamon(lambda: schedule_job(time_list, 5, job))


main()
