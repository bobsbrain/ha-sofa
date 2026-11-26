# Sofa für Home Assistant

Bindet [Sofa](https://github.com/bobsbrain/sofa) – das Stöber-Frontend für MediathekViewWeb – als **Medienquelle** in Home Assistant ein.

- In der Seitenleiste unter **Medien → Sofa** erscheinen die Reihen der Sofa-Startseite (Weiterschauen, Merkliste, Neue Folgen deiner Sendungen, Für dich ausgesucht, Genres …), alle Genres und deine gefolgten Sendungen bis hinunter zu den einzelnen Folgen.
- Abspielen auf jedem Medienplayer, den Home Assistant kennt (Chromecast, Google TV, Fernseher mit Cast …).
- In Automationen und Skripten nutzbar über `media-source://sofa/…` (z. B. `media-source://sofa/item/<id>`).
- Was über Home Assistant läuft, meldet die Integration als Fortschritt an Sofa zurück – *Weiterschauen* und die Empfehlungen bleiben aktuell.

## Voraussetzungen

- Ein laufender Sofa-Server, den Home Assistant erreichen kann
- Home Assistant 2025.1 oder neuer

## Installation

**Über den Store (HACS):** dieses Repository als benutzerdefiniertes Repository vom Typ *Integration* hinzufügen, „Sofa“ installieren, Home Assistant neu starten.

**Manuell:** den Ordner `custom_components/sofa` nach `<config>/custom_components/sofa` kopieren und Home Assistant neu starten.

Danach unter **Einstellungen → Geräte & Dienste → Integration hinzufügen → Sofa** die Adresse des Sofa-Servers eintragen, z. B. `https://sofa.example.org`.

## Hinweise

- Abgespielt wird direkt vom Sender (MP4 oder HLS). Inhalte, die nur in Österreich oder der Schweiz abrufbar sind, werden nicht angeboten.
- Eine Suche gibt es im Medien-Bereich von Home Assistant für solche Quellen nicht; gesucht wird in Sofa.
- Bei HLS-Streams im CMAF-Format (z. B. ARTE) hängt es vom Empfangsgerät ab, ob sie über Home Assistant abspielen; in Sofa selbst funktionieren sie immer.
