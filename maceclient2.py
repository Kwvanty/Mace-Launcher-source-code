import asyncio
import websockets


# ==========================================
# Настройки
# ==========================================

SERVER_URL = "ws://127.0.0.1:8000/ws"


# ==========================================
# Получение сообщений
# ==========================================

async def receive_messages(websocket):

    try:

        while True:

            message = await websocket.recv()

            print(f"\n{message}")

    except websockets.exceptions.ConnectionClosed:

        print(
            "\n[MaceClient] "
            "Соединение с сервером закрыто"
        )


# ==========================================
# Основная функция
# ==========================================

async def main():

    print("===================================")
    print("          MaceClient")
    print("===================================\n")


    # ==========================================
    # Ввод имени
    # ==========================================

    username = input(
        "Введите имя: "
    ).strip()


    if not username:

        print(
            "[MaceClient] "
            "Имя не может быть пустым"
        )

        return


    print(
        "\n[MaceClient] "
        "Подключение к MaceHost..."
    )


    try:

        async with websockets.connect(
            SERVER_URL
        ) as websocket:


            # ==========================================
            # Отправляем имя серверу
            # ==========================================

            await websocket.send(username)


            print(
                "[MaceClient] "
                "Подключено!"
            )

            print(
                "Введите сообщение."
            )

            print(
                "Для выхода: /exit\n"
            )


            # ==========================================
            # Запускаем получение сообщений
            # ==========================================

            receive_task = asyncio.create_task(
                receive_messages(websocket)
            )


            # ==========================================
            # Отправка сообщений
            # ==========================================

            while True:

                message = await asyncio.to_thread(
                    input,
                    "Вы: "
                )


                # Выход
                if message.lower() == "/exit":

                    print(
                        "[MaceClient] "
                        "Отключение..."
                    )

                    break


                # Отправка сообщения
                await websocket.send(message)


            # Останавливаем задачу
            receive_task.cancel()


    except Exception as error:

        print(
            f"\n[MaceClient] "
            f"Ошибка подключения:\n{error}"
        )


# ==========================================
# Запуск
# ==========================================

if __name__ == "__main__":

    asyncio.run(main())