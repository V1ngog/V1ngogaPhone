import asyncio
import json
import websockets
import logging
import sys

# Настройка логов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Постоянный ID
ROOM_ID = "my_permanent_room"

# Комната
room = {
    "clients": [],  # максимум 2 клиента
    "creator": None
}

async def kick_both_users(reason="Kicked by server"):
    """Кикает обоих пользователей с сервера"""
    if len(room["clients"]) < 2:
        logger.warning("⚠️ В комнате меньше 2 пользователей, некого кикать")
        return False
    
    # Копируем список клиентов, чтобы избежать проблем при удалении
    clients_to_kick = room["clients"].copy()
    kicked_count = 0
    
    for client in clients_to_kick:
        try:
            await client.send(json.dumps({
                "type": "kicked",
                "reason": reason
            }))
            await client.close(code=1000, reason=reason)
            kicked_count += 1
            logger.info(f"✅ Клиент {str(id(client))[-4:]} кикнут")
        except Exception as e:
            logger.error(f"❌ Ошибка при кике клиента: {e}")
    
    # Очищаем комнату
    room["clients"].clear()
    room["creator"] = None
    
    logger.info(f"💥 Оба пользователя кикнуты! Причина: {reason}")
    logger.info(f"🏠 Комната очищена, ждем новых подключений")
    return True

async def console_listener():
    """Слушает команды из консоли"""
    logger.info("=" * 60)
    logger.info("🎮 КОМАНДЫ КОНСОЛИ:")
    logger.info("  - kick [причина]  : Кикнуть обоих пользователей")
    logger.info("  - status          : Показать статус комнаты")
    logger.info("  - clear           : Очистить экран")
    logger.info("  - exit            : Остановить сервер")
    logger.info("=" * 60)
    
    while True:
        try:
            # Асинхронный ввод из консоли
            command = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: input("\n📝 Введите команду: ")
            )
            
            command = command.strip().lower()
            
            if command.startswith("kick"):
                # Разбираем команду: "kick Причина кика"
                parts = command.split(" ", 1)
                reason = parts[1] if len(parts) > 1 else "Kicked by admin"
                
                logger.info(f"🔨 Получена команда КИК с причиной: {reason}")
                await kick_both_users(reason)
                
            elif command == "status":
                logger.info(f"📊 СТАТУС КОМНАТЫ:")
                logger.info(f"  - Клиентов: {len(room['clients'])}/2")
                if room["clients"]:
                    for i, client in enumerate(room["clients"], 1):
                        client_id = str(id(client))[-4:]
                        is_creator = "👑" if client == room["creator"] else ""
                        logger.info(f"  - Клиент {i}: {client_id} {is_creator}")
                else:
                    logger.info("  - Комната пуста")
                logger.info(f"  - Создатель: {str(id(room['creator']))[-4:] if room['creator'] else 'Нет'}")
                
            elif command == "clear":
                # Очистка консоли
                if sys.platform == "win32":
                    import os
                    os.system('cls')
                else:
                    import os
                    os.system('clear')
                logger.info("🔄 Экран очищен")
                
            elif command == "exit":
                logger.info("👋 Остановка сервера...")
                sys.exit(0)
                
            elif command == "help":
                logger.info("🎮 ДОСТУПНЫЕ КОМАНДЫ:")
                logger.info("  - kick [причина]  : Кикнуть обоих пользователей")
                logger.info("  - status          : Показать статус комнаты")
                logger.info("  - clear           : Очистить экран")
                logger.info("  - exit            : Остановить сервер")
                
            elif command == "":
                # Игнорируем пустые команды
                pass
                
            else:
                logger.warning(f"❌ Неизвестная команда: {command}. Введите 'help' для списка команд")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке команды: {e}")

async def handler(websocket):
    """Обработчик подключения."""
    client_id = str(id(websocket))[-4:]
    logger.info(f"🔗 Клиент {client_id} подключился")
    
    try:
        # Добавляем клиента в комнату
        if len(room["clients"]) >= 2:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Комната уже полна"
            }))
            await websocket.close()
            logger.warning(f"❌ Клиент {client_id} отклонен - комната полна")
            return
        
        # Запоминаем клиента
        room["clients"].append(websocket)
        
        # Первый клиент
        if len(room["clients"]) == 1:
            room["creator"] = websocket
            await websocket.send(json.dumps({
                "type": "room_ready",
                "role": "creator",
                "message": "Ты первый! Ждём друга..."
            }))
            logger.info(f"👑 Клиент {client_id} создатель (ждёт)")
        
        # Второй клиент
        elif len(room["clients"]) == 2:
            await websocket.send(json.dumps({
                "type": "room_ready",
                "role": "joiner",
                "message": "Ты подключился! Начинаем звонок..."
            }))
            
            # Оповещаем всех, что оба готовы
            for client in room["clients"]:
                await client.send(json.dumps({
                    "type": "both_ready"
                }))
            
            logger.info(f"🎉 Оба клиента в комнате! Начинаем звонок!")
        
        # Обработка сообщений
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action")
                logger.info(f"📨 {client_id} -> {action}")
                
                if action == "signal":
                    payload = data.get("payload")
                    # Отправляем другому клиенту
                    for client in room["clients"]:
                        if client != websocket:
                            try:
                                await client.send(json.dumps({
                                    "type": "signal",
                                    "payload": payload
                                }))
                            except:
                                pass
                
                elif action == "leave":
                    logger.info(f"🚪 Клиент {client_id} вышел")
                    await websocket.send(json.dumps({
                        "type": "left",
                        "message": "Ты вышел"
                    }))
                    break
                
                elif action == "ping":
                    # Ответ на ping для проверки соединения
                    await websocket.send(json.dumps({
                        "type": "pong"
                    }))
                    
            except json.JSONDecodeError:
                logger.warning(f"⚠️ Некорректный JSON от {client_id}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Некорректный JSON"
                }))
    
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"🔌 Клиент {client_id} отключился")
    
    except Exception as e:
        logger.error(f"💥 Ошибка в обработчике {client_id}: {e}")
    
    finally:
        # Убираем клиента из комнаты
        if websocket in room["clients"]:
            room["clients"].remove(websocket)
            
            # Если комната опустела
            if len(room["clients"]) == 0:
                room["creator"] = None
                logger.info(f"🏠 Комната пуста, ждём новых клиентов")
            else:
                # Уведомляем оставшегося клиента
                for client in room["clients"]:
                    try:
                        await client.send(json.dumps({
                            "type": "peer_disconnected",
                            "message": "Собеседник вышел"
                        }))
                        logger.info(f"📤 Отправлено peer_disconnected клиенту {str(id(client))[-4:]}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки peer_disconnected: {e}")

async def main():
    host = "0.0.0.0"
    port = 8765
    
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК СЕРВЕРА СИГНАЛИЗАЦИИ")
    logger.info("=" * 60)
    logger.info(f"🌐 Адрес: ws://{host}:{port}")
    logger.info(f"🏠 Комната: {ROOM_ID}")
    logger.info("=" * 60)
    
    # Создаем сервер
    server = await websockets.serve(handler, host, port)
    
    # Запускаем параллельно:
    # 1. Ожидание сервера
    # 2. Прослушивание консольных команд
    await asyncio.gather(
        server.wait_closed(),
        console_listener()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Сервер остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")