Gezichten Vervagen  v{{VERSION}}  ({{DATE}})
==================================================================
Nederlands below / English below the Dutch part.

WAT IS DIT?
Een tool om gezichten op (school)foto's te vervagen. De tool zoekt alle
gezichten op; jij klikt aan wie niet herkenbaar mag zijn. Alles gebeurt in je
eigen browser: er wordt niets geüpload en er is geen account nodig.

OPENEN
1. Pak de ZIP eerst uit (rechtermuisknop > "Alles uitpakken" op Windows;
   dubbelklik op macOS; "Uitpakken hier" op Linux). Dat mag ook op een USB-stick.
2. Dubbelklik op  gezichten-vervagen.html.  Hij opent in je standaardbrowser.
   Een andere browser kiezen: rechtermuisknop > "Openen met".

Beste ervaring: Chrome of Edge (Windows, macOS, Linux).
Firefox en Safari werken ook; de export gaat dan als ZIP-download.
Bij grote exports krijg je meerdere ZIP-bestanden. Vraagt je browser of de pagina
"meerdere bestanden mag downloaden", kies dan "Toestaan".

GEBRUIK IN HET KORT
  01 Laden       Sleep een map met foto's (JPG, PNG, WebP) in het venster.
  02 Beoordelen  Klik op de gezichten die vervaagd moeten worden.
                 "Per foto": sleep een kader om een gemist gezicht toe te voegen;
                 een kader weghalen kan met de x of de Delete-toets.
  03 Exporteren  Sla de nieuwe foto's op. Je originelen blijven onaangeroerd.
                 Met "Sessie opslaan" ga je later verder (het sessiebestand bevat
                 alleen bestandsnamen en coördinaten, geen foto's).

PRIVACY
- Detectie, geen herkenning: de tool weet waar gezichten staan, niet wie het is.
- Een ingebouwd beveiligingsbeleid (Content-Security-Policy, bovenin het
  HTML-bestand) verbiedt de pagina om gegevens naar een server te sturen.
  Controleer het zelf: F12 > tabblad Netwerk.
- Browserextensies vallen buiten dat beleid. Voor maximale zekerheid: gebruik
  een browserprofiel zonder extensies.
- Geëxporteerde foto's bevatten geen metadata meer (geen GPS, geen cameragegevens).
- Deze tool vervangt geen toestemmingsbeleid. Bekijk elke foto voor publicatie.

BEKENDE BEPERKINGEN
- Gezichten die opzij liggen, sterk weggedraaid of half bedekt zijn, worden soms
  gemist. Voeg ze met de hand toe.
- HEIC-foto's (iPhone) worden niet ondersteund; exporteer ze eerst als JPG.
- Telefoons en tablets zijn niet getest.

CONTROLEREN / NIEUWSTE VERSIE
De SHA-256-controlesom van gezichten-vervagen.html staat in SHA256SUMS.txt en op
{{BASE_URL}}
  Windows (PowerShell):  Get-FileHash .\gezichten-vervagen.html -Algorithm SHA256
  macOS:                 shasum -a 256 gezichten-vervagen.html
  Linux:                 sha256sum gezichten-vervagen.html
De tool controleert zelf nooit op updates (hij maakt geen enkele verbinding).
Je versienummer staat linksonder in de tool.

Licentie: zie LICENSE.txt. Onderdelen van derden: zie THIRD-PARTY-NOTICES.txt.
Homegrown IT Consulting


==================================================================
ENGLISH

WHAT IS THIS?
A tool to blur faces in (school) photos. It finds all faces; you click the ones
that must not be recognisable. Everything happens in your own browser: nothing
is uploaded and no account is needed.

OPENING
1. Unzip the ZIP first (right-click > "Extract All" on Windows; double-click on
   macOS; "Extract here" on Linux). A USB stick is fine.
2. Double-click  gezichten-vervagen.html.  It opens in your default browser.
   To pick another browser: right-click > "Open with".

Best experience: Chrome or Edge (Windows, macOS, Linux).
Firefox and Safari work too; the export then arrives as a ZIP download.
Large exports come as several ZIP files. If your browser asks whether the page
may "download multiple files", choose "Allow".

QUICK GUIDE
  01 Load     Drop a folder of photos (JPG, PNG, WebP) onto the window.
  02 Review   Click the faces to blur.
              "Per photo": drag a box to add a missed face; remove a box with
              its x or the Delete key.
  03 Export   Save the new photos. Your originals stay untouched.
              "Save session" lets you continue later (the session file holds
              only file names and coordinates, no photos).

PRIVACY
- Detection, not recognition: the tool knows where faces are, not who they are.
- A built-in security policy (Content-Security-Policy, at the top of the HTML
  file) forbids the page to send data to any server. Check it yourself:
  F12 > Network tab.
- Browser extensions fall outside that policy. For maximum certainty, use a
  browser profile without extensions.
- Exported photos contain no metadata (no GPS, no camera details).
- This tool does not replace a consent policy. Check every photo before publishing.

KNOWN LIMITATIONS
- Faces lying sideways, turned far away or half covered are sometimes missed.
  Add them by hand.
- HEIC photos (iPhone) are not supported; export them as JPG first.
- Phones and tablets have not been tested.

VERIFY / LATEST VERSION
The SHA-256 checksum of gezichten-vervagen.html is in SHA256SUMS.txt and at
{{BASE_URL}}
(commands above). The tool never checks for updates itself (it makes no
connections at all). Your version number is shown at the bottom left of the tool.

Licence: see LICENSE.txt. Third-party components: see THIRD-PARTY-NOTICES.txt.
Homegrown IT Consulting
