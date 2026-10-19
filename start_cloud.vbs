Set WshShell = CreateObject("WScript.Shell")

' Путь к проекту
ProjectPath = "A:\CloudStorage"

' Команда для запуска
Command = "cmd /c cd /d " & ProjectPath & " && call .venv\Scripts\activate.bat && python app.py"

' Запуск в скрытом окне
WshShell.Run Command, 0, False

' Сообщение
MsgBox "CloudStorage запущен!" & vbCrLf & vbCrLf & _
       "Сервер доступен по адресу:" & vbCrLf & _
       "https://localhost:443", vbInformation, "CloudStorage"