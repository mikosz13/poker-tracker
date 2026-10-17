# Najczęstsze pytania

## Gdzie są moje dane i czy coś wychodzi poza komputer? {#data}

Wszystko jest u Ciebie, w jednym pliku bazy:

- macOS: `~/Library/Application Support/PokerTracker/pokertracker.db`
- Windows: `%APPDATA%\PokerTracker\pokertracker.db`

Aplikacja nie wysyła nigdzie żadnych danych: nie ma konta, logowania, statystyk użycia ani reklam. Jej okno rozmawia tylko z małym serwerem na Twoim komputerze (`127.0.0.1`), niedostępnym z sieci. Plików z PokerCraft nie zmienia ani nie kopiuje; czyta je z folderu, który wskażesz. Internet jest potrzebny tylko Tobie: do pobrania eksportów z PokerCraft i nowej wersji aplikacji, a także gdy sam klikniesz link do GitHuba.

## Jak zrobić kopię i przenieść dane na inny komputer? {#move}

1. Na starym komputerze: **Ustawienia → Kopia zapasowa → Zrób kopię**. W folderze Pobrane pojawi się plik z datą, np. `poker-tracker-2026-10-17.db`.
2. Przenieś ten plik na nowy komputer (pendrive, dysk w chmurze, e-mail do siebie).
3. Na nowym komputerze zainstaluj aplikację, otwórz **Ustawienia → Przywróć z kopii**, wskaż plik i potwierdź. Aplikacja sprawdzi plik, zapisze obecną bazę obok i wczyta kopię; starszą kopię od razu zaktualizuje.

Możesz też po prostu zaimportować na nowym komputerze te same pliki z PokerCraft; wynik będzie ten sam, ale PokerCraft daje historie rąk tylko z ostatnich 90 dni, więc kopia jest pewniejsza.

## Jak zaktualizować aplikację? {#update}

Pobierz nową wersję ze strony [Releases na GitHubie](https://github.com/mikosz13/poker-tracker/releases) i zastąp nią starą (macOS: przeciągnij do Aplikacji i wybierz „Zastąp”; Windows: rozpakuj w miejsce starego folderu). Dane są osobno, w folderze opisanym wyżej, więc zostają. Przy pierwszym uruchomieniu nowa wersja sama zaktualizuje bazę i zostawi obok kopię sprzed aktualizacji (`pokertracker.db.bak-v…`). Co się zmieniło, mówi [O aplikacji](#/help/about/changes).

## Jak usunąć moje dane? {#delete}

- **Jeden turniej**: na jego stronie **Ignoruj turniej**. Znika ze wszystkich wyników i nie wróci przy następnym imporcie; przywrócisz go w Ustawieniach.
- **Wszystko**: zamknij aplikację i usuń folder z danymi (ścieżki wyżej). Zniknie baza, kopie sprzed aktualizacji i dane przykładowe (`demo.db`). Przy następnym uruchomieniu aplikacja zacznie od pustej bazy.
- Usunięcie samej aplikacji nie usuwa danych, a usunięcie danych nie rusza Twoich plików z PokerCraft.

## Czy aplikacja działa bez internetu? {#offline}

Tak, w całości. Wszystko, co pokazuje, łącznie z tą Pomocą, jest w aplikacji; nie ładuje niczego z sieci. Bez internetu nie pobierzesz tylko nowych eksportów z PokerCraft.

## Czy aplikacja zna moje hasło do GGPoker? {#account}

Nie. Nie łączy się z GGPoker ani z PokerCraft; czyta wyłącznie pliki, które sam pobierzesz i wskażesz.
