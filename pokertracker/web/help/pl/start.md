# Pierwsze kroki

## Pliki i import {#import}

Aplikacja czyta dwa rodzaje plików z **PokerCraft** (GGPoker): **historie rąk** i **podsumowania turniejów**, jako .txt albo .zip (PDF z warstwą tekstową też działa). PokerCraft pozwala pobrać około dziesięciu turniejów naraz, a historie rąk tylko z ostatnich 90 dni, więc importuj po każdej sesji.

W **Imporcie** wybierz folder z plikami: podgląd pokaże turnieje, odznacz te, których nie chcesz, i importuj. Z „Obserwuj ten folder” nowe eksporty wczytują się same, gdy aplikacja jest otwarta. Ponowny import tych samych plików niczego nie zmienia; „Wczytaj wszystkie pliki od nowa” odbudowuje wszystko z plików (potrzebne tylko po aktualizacji).

Pomijane, z podanym powodem: cash, Sit & Go, PLO, turnieje w innych walutach, freerolle i promocje (buy-in 0 $) oraz podsumowania, których aplikacja nie rozpoznaje (bezpiecznik na zmianę formatu GG). Turnieje, które sam zignorujesz, przywrócisz w Ustawieniach.

**Dane przykładowe**: przycisk na pustym Pulpicie (i w Ustawieniach) otwiera aplikację na 40 zmyślonych turniejach w osobnej bazie `demo.db`, obok Twojej. Twoja baza zostaje nietknięta; import i kopie zapasowe są wtedy wyłączone, a pasek u góry wraca do Twoich danych jednym kliknięciem.

## Pulpit {#dashboard}

Na górze **ostatnia sesja**: turnieje z przerwami krótszymi niż trzy godziny. „Szczegóły sesji” otwierają jej ekran: szczęście w all-inach, sesję wobec Twojej normy, odpadnięcia, bad beaty i największe pule do przejrzenia.

Niżej **okres**: ostatnia sesja, 24 godziny, 7, 14 albo 30 dni, a pod „Więcej” 3 lub 6 miesięcy, cała historia i własne daty. Cztery kafelki: zysk (bilety po wartości nominalnej, pod spodem część gotówkowa), ROI, turnieje i szczęście. Jeden wykres przełącza się między zyskiem w $ a wynikiem w BB ze szczęściem i bez. „Warto wiedzieć” podaje najlepszy turniej, wygrane bilety i to, czy Twoja gra zmieniła się ponad szum.

## Turnieje {#tournaments}

Listę filtrujesz okresem, buy-inem, formatem i wejściem (od startu albo late reg). Strona turnieju pokazuje miejsce, nagrodę, koszt i ROI, każde wejście z poziomem i stackiem startowym oraz ostrzeżenie, gdy pliki pokazują mniej wejść niż podsumowanie.

**Wykres stacku** przełączasz między big blindami a żetonami (głęboki run może rosnąć w żetonach, a spadać w BB). Każdy all-in to kropka: zielona wygrany, czerwona przegrany, szara podział; dymek pokazuje karty, Twoje equity i szczęście. Kliknięcie otwiera rękę.

**Turnieje wielodniowe**: każdy flight dnia 1 z awansem łączy się ze swoim Day 2 w jeden turniej (koszt wszystkich flightów, jedno miejsce końcowe). Gdy PokerCraft daje ręce z Day 2, ale nie podsumowanie, wydarzenie liczy to, co znane, i jest oznaczone; `pokertracker provisional <id> <kwota>` liczy wpisaną nagrodę, dopóki podsumowanie jej nie zastąpi.

## Ręce i replayer {#hands}

**Ręce** wyszukują ręce po okresie, buy-inie, formacie, pozycji, rękach startowych (klik albo przeciągnięcie po siatce), stacku w BB, akcji preflop, all-inie, showdownie i wyniku (faktycznym albo wg EV). Akcje preflop to definicje z Analizy, więc „3-bet” znajduje dokładnie te ręce, które liczy Analiza.

Kliknięcie otwiera **replayer**: przechodzisz przez rękę krok po kroku, odtwarzasz ją i widzisz equity przy każdym all-inie. Pod nim poprzedni i następny wynik wyszukiwania. „Kopiuj rękę” daje tekst na forum: pozycje zamiast nicków rywali, stacki w BB, każda ulica, wynik.

## Kopia zapasowa i eksport {#backup}

**Ustawienia → Kopia zapasowa**: „Zrób kopię” zapisuje całą bazę z datą w Pobranych. „Przywróć z kopii” najpierw sprawdza plik, zapisuje obecną bazę obok, a potem ją zastępuje; starszą kopię od razu aktualizuje.

**Eksport CSV** na liście turniejów i w Rękach zapisuje to, co widać, do Pobranych, dla Excela. „Kopiuj wynik” i „Kopiuj rękę” dają zwykły tekst. Nagroda tymczasowa jest wszędzie oznaczona.
