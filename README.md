# Светлячок («Изгиб Питона»)

Детская игра-змейка про энергосбережение. Змейка Питоша собирает лампочки,
и в домиках на заднем плане загораются окна.

Играть онлайн: https://dxbrkt.github.io/snake-svetlyachok/

## Запуск на компьютере

```bash
pip install pygame
python the_snake.py
```

Управление: стрелки (или WASD), на телефоне — свайпы. P или пробел — пауза.

## Веб-версия

`tools/build_web.sh` собирает игру через pygbag в папки `build/web` и `docs/`
(из `docs/` работает GitHub Pages).

## Графика и шрифт

Спрайты вырезаны из листа ассетов скриптом `tools/build_assets.py`.
Шрифт Marmelad — SIL Open Font License 1.1.
