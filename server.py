import asyncio
import json
import websockets
import logging

# Логи
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Постоянный ID
ROOM_ID = "my_permanent_room"

# Комната
room = {
    "clients": [],  # максимум 2 клиента
    "creator": None
}


async def handler(websocket):
    #Обработчик подключения.

    client_id = str(id(websocket))[-4:]  # id клиента
    logger.info(f"Клиент {client_id} подключился")
    
    try:
        # Добавляем клиента в комнату
        if len(room["clients"]) >= 2:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Комната уже полна"
            }))
            await websocket.close()
            return
        
        # Запоминаем
        room["clients"].append(websocket)
        
        # первый клиент
        if len(room["clients"]) == 1:
            room["creator"] = websocket
            await websocket.send(json.dumps({
                "type": "room_ready",
                "role": "creator",
                "message": "Ты первый! Ждём друга..."
            }))
            logger.info(f"{client_id} создатель (ждёт)")
        
        # второй клиент
        elif len(room["clients"]) == 2:
            await websocket.send(json.dumps({
                "type": "room_ready",
                "role": "joiner",
                "message": "Ты подключился! Начинаем звонок..."
            }))
            
            # Оповещаем всех
            for client in room["clients"]:
                await client.send(json.dumps({
                    "type": "both_ready"
                }))
            
            logger.info(f"Оба клиента в комнате!")
        
        # Обработка сообщений
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action")
                logger.info(f"{client_id} -> {action}")
                if action == "signal":
                    payload = data.get("payload")
                    # Отправляем всем
                    for client in room["clients"]:
                        if client != websocket:
                            try:
                                await client.send(json.dumps({
                                    "type": "signal",
                                    "payload": payload
                                }))
                            except:
                                pass
                
                # Выход
                elif action == "leave":
                    await websocket.send(json.dumps({
                        "type": "left",
                        "message": "Ты вышел"
                    }))
                    break
                    
            except json.JSONDecodeError:
                logger.warning(f" Некорректный JSON от {client_id}")
    
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Клиент {client_id} отключился")
    
    finally:
        # Убираем клиента из комнаты 
        if websocket in room["clients"]:
            room["clients"].remove(websocket)
            
            #сбрасываем создателя
            if len(room["clients"]) == 0:
                room["creator"] = None
                logger.info(f"Комната пуста, ждём новых")
            else:
                logger.info(f"Отправляем peer_disconnected оставшемуся клиенту")
        
                # Оповещаем что друг вышел
                for client in room["clients"]:
                    try:
                        await client.send(json.dumps({
                            "type": "peer_disconnected",
                            "message": "Собеседник вышел"
                        }))
                    except:
                        pass


async def main():
    host = "0.0.0.0"
    port = 8765
    
    logger.info(f"🚀 Сервер сигнализации запущен на ws://{host}:{port}")
    logger.info(f"🏠 Постоянная комната: {ROOM_ID}")
    
    async with websockets.serve(handler, host, port):
        await asyncio.Future()  #ожидание


if __name__ == "__main__":
    asyncio.run(main())