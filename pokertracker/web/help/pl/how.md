# Jak liczymy

## Analiza {#analysis}

Każdy wskaźnik liczymy od jego własnych okazji, tak jak PokerTracker 4, a pod nim jest n (liczba okazji); poniżej 30 okazji jest szary.

- **VPIP**: dobrowolnie wkładasz żetony preflop (call, bet, raise; complete z SB tak, check z BB nie). Mianownik: ręce z decyzją preflop, bez spacerów i all-inów wymuszonych blindem.
- **PFR**: podbijasz preflop (limp-raise też).
- **RFI**: podbijasz, gdy wszyscy przed Tobą spasowali (bez limperów); nigdy z BB.
- **Open shove**: ten raise to all-in; liczony od okazji RFI przy tym samym stacku.
- **3-bet**: przed Twoją pierwszą decyzją był dokładnie jeden raise (squeeze też), a Ty przebijasz. All-in, którego nie możesz przebić, nie jest okazją; all-in za mniej, niż masz, jest (izolacja).
- **Fold to 3-bet**: Twój open (nie all-in) został raz przebity, a Ty pasujesz.
- **bb/100 wg EV**: wynik na 100 rąk, w którym EV all-ina zastępuje faktyczny wynik.

**Trend** porównuje ostatnie 30 dni z resztą historii (co najmniej 500 rąk i 100 okazji po obu stronach) i pokazuje strzałkę tylko przy zmianie ponad szum (|z| ≥ 2,5), najwyżej jedną naraz.

**Leaki i mocne strony** testują każdy spot wg EV wobec punktu odniesienia (call z blindów wobec foldu) i korygują wszystkie naraz: karta pojawia się tylko przy q ≤ 0,05. Spoty najbliżej progu są na osobnej liście, nadal w granicach przypadku. **Siatka rąk startowych** pokazuje każdą rękę wg EV wobec jej spasowania; szara poniżej 30 rąk. **Linie showdownu** dzielą wynik na ręce z showdownem i resztę.

**Wariancja**: 10 000 symulacji następnych 100, 500 albo 1000 turniejów losowanych z Twoich własnych (bootstrap, wyniki w buy-inach). Pokazuje typowy wynik i rozrzut, szansę na stratę, największy dołek i ile buy-inów trzyma ryzyko większego dołka poniżej 5%; suwak „co jeśli ROI” skaluje nagrody. Nie widzi zmian w Twojej grze, polach ani strukturach; poniżej 100 turniejów jest wyraźna uwaga.

**Sesje**: VPIP, PFR, bb/100 wg EV i ROI według liczby turniejów naraz, pory dnia i czasu od początku sesji (sesja kończy się po przerwie dłuższej niż 3 h, jak na Pulpicie). Każda grupa jest porównana z Twoimi pozostałymi rękami przy tym samym stacku, a niepewność liczona sesjami, nie rękami; pokazujemy tylko różnice ponad szum.

## Finanse {#money}

**ROI** liczy bilety po wartości nominalnej po obu stronach: satelita zwraca wartość miejsca, a turniej opłacony biletem kosztuje pełny buy-in, więc suma zgadza się z przepływem gotówki; „w tym gotówka” pomija bilety. Przy każdym ROI jest **przedział 95%** (bootstrap po Twoich turniejach): tam prawdopodobnie leży Twoje długoterminowe ROI. Grupa jest na plusie lub minusie tylko wtedy, gdy cały przedział leży nad lub pod zerem.

**ITM** (dojście do miejsc płatnych) liczymy tylko tam, gdzie mówią to pliki: turnieje bez bounty i satelity (bilet to ITM). Podsumowanie bounty podaje jedną kwotę za miejsce i nokauty, więc pieniądze z bounty liczą się w zysku i ROI, ale nie w ITM. **Top 10% / 15% pola** to zwykłe fakty: Twoje miejsce do liczby graczy. Late reg poprawia miejsce, więc tabela late reg porównuje ROI.

## Jak liczymy szczęście {#luck}

{{luck}}
