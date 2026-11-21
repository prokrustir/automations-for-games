@echo off
rem Uruchamia FMRTE bez podnoszenia uprawnien (bez okna UAC).
set __COMPAT_LAYER=RunAsInvoker
start "" /D "d:\gry\fmrte 26\current" "d:\gry\fmrte 26\current\fmrte.exe"
