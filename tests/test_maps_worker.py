"""Unit tests for the fast feed-HTML MapsWorker parser."""

from core.maps_worker import parse_feed_html, parse_single_place_html, _parse_rating_and_reviews


SAMPLE_FEED_HTML = """
<div role="feed">
  <div>
    <a href="https://www.google.com/maps/place/Kopi+Merapi/data=!4m7!3m6!1sChIJ12345abcde!8m2!3d-7.7!4d110.3" aria-label="Kopi Merapi"></a>
    <div class="fontHeadlineSmall">Kopi Merapi</div>
    <span class="fontBodyMedium">
      <span aria-label="4,7 bintang 320 ulasan"></span>
    </span>
    <div class="fontBodyMedium">
      <div></div>
      <div>
        <div><span>Kedai Kopi · Jl. Kaliurang KM 8, Yogyakarta</span></div>
        <div><span>Buka 24 jam · 0812-3456-7890</span></div>
      </div>
    </div>
    <a data-value="Website" href="https://kopimerapi.id">Website</a>
  </div>
  <div>
    <a href="https://www.google.com/maps/place/Kopi+Merapi/data=!4m7!3m6!1sChIJ12345abcde" aria-label="Kopi Merapi"></a>
    <div class="fontHeadlineSmall">Kopi Merapi</div>
  </div>
  <div>
    <a href="https://www.google.com/maps/place/Cafe+Klaten+Asri/data=!4m7!3m6!1sChIJ99999xyz" aria-label="Cafe Klaten Asri"></a>
    <div class="fontHeadlineSmall">Cafe Klaten Asri</div>
    <span class="fontBodyMedium">
      <span aria-label="4.5 stars 1,240 reviews"></span>
    </span>
    <div class="fontBodyMedium">
      <div>
        <div><span>Kafe · Jl. Pemuda No. 12, Klaten</span></div>
        <div><span>Tutup pukul 22.00 · +62 272 555123</span></div>
      </div>
    </div>
  </div>
</div>
"""


def test_parse_rating_and_reviews_variants():
    assert _parse_rating_and_reviews("4,7 bintang 320 ulasan") == (4.7, 320)
    assert _parse_rating_and_reviews("4.5 stars 1,240 reviews") == (4.5, 1240)
    assert _parse_rating_and_reviews(None, "4,8", "(89)") == (4.8, 89)


def test_parse_feed_html_extracts_and_deduplicates():
    items = parse_feed_html(SAMPLE_FEED_HTML, limit=None)
    assert len(items) == 2

    items_limited = parse_feed_html(SAMPLE_FEED_HTML, limit=1)
    assert len(items_limited) == 1

    first = items[0]
    assert first["business_name"] == "Kopi Merapi"
    assert first["place_id"] == "ChIJ12345abcde"
    assert first["category"] == "Kedai Kopi"
    assert first["address"] == "Jl. Kaliurang KM 8, Yogyakarta"
    assert first["phone_raw"] == "0812-3456-7890"
    assert first["website_raw"] == "https://kopimerapi.id"
    assert first["rating"] == 4.7
    assert first["reviews_count"] == 320

    second = items[1]
    assert second["business_name"] == "Cafe Klaten Asri"
    assert second["rating"] == 4.5
    assert second["reviews_count"] == 1240
    assert second["phone_raw"] == "+62 272 555123"


def test_parse_single_place_html():
    html = """
    <html><body>
      <h1>Cafe Magelang View</h1>
      <button data-item-id="address"> Jl. Soekarno Hatta No. 5, Magelang</button>
      <button data-item-id="phone:tel:081987654321"> 0819-8765-4321</button>
      <a data-item-id="authority" href="https://magelangview.com">Site</a>
      <button jsaction="pane.rating.category">Kafe</button>
      <span role="img" aria-label="4,6 bintang 85 ulasan"></span>
    </body></html>
    """
    item = parse_single_place_html(html, "https://www.google.com/maps/place/Cafe/ChIJabc")
    assert item is not None
    assert item["business_name"] == "Cafe Magelang View"
    assert item["place_id"] == "ChIJabc"
    assert item["category"] == "Kafe"
    assert item["address"] == "Jl. Soekarno Hatta No. 5, Magelang"
    assert item["phone_raw"] == "0819-8765-4321"
    assert item["website_raw"] == "https://magelangview.com"
    assert item["rating"] == 4.6
    assert item["reviews_count"] == 85
