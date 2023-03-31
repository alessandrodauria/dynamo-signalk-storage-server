const style = {
  Point: new ol.style.Style({
    image: new ol.style.Circle({
      fill: new ol.style.Fill({
        color: "rgba(250,128,114)",
      }),
      radius: 20,
      stroke: new ol.style.Stroke({
        color: "#ff0",
        width: 1,
      }),
    }),
  }),
  LineString: new ol.style.Style({
    stroke: new ol.style.Stroke({
      color: "#f05",
      width: 3,
    }),
  }),
  MultiLineString: new ol.style.Style({
    stroke: new ol.style.Stroke({
      color: "#0f0",
      width: 3,
    }),
  }),
};

var mapView = new ol.View({
  center: ol.proj.fromLonLat([23.506092, 60.045847]),
  zoom: 12,
});

var map = new ol.Map({
  target: "map",
  view: mapView,
});

var osmTile = new ol.layer.Tile({
  title: "Map",
  visible: true,
  source: new ol.source.OSM(),
});

let gpxSource =
  "gpx/vessels.urn%3Amrn%3Aimo%3Ammsi%3A247440700?start=20230118Z100000&hours=1";

const vectorGPX = new ol.layer.Vector({
  source: new ol.source.Vector({
    url: gpxSource,
    format: new ol.format.GPX(),
  }),
  style: function (feature) {
    return style[feature.getGeometry().getType()];
  },
});

const vectorGEOJSON = new ol.layer.Vector({
  source: new ol.source.Vector({
    url: "https://d2ad6b4ur7yvpq.cloudfront.net/naturalearth-3.3.0/ne_10m_airports.geojson",
    format: new ol.format.GeoJSON(),
  }),
  style: function (feature) {
    return style[feature.getGeometry().getType()];
  },
});

//

// inserire tutte le proprietà che si vogliono visualizzare
const overlayContainerElement = document.querySelector(".overlay-container");

map.on("click", function (e) {
  map.forEachFeatureAtPixel(e.pixel, function (feature, layer) {
    let clickedFeaturedName = feature.get("name");
    let clickedFeaturedType = feature.get("type");
    let clickedFeaturedAdditionalInfo = feature.get("additionalInfo");

    console.log(
      clickedFeaturedName,
      clickedFeaturedType,
      clickedFeaturedAdditionalInfo
    );
  });
});

map.addLayer(osmTile);
map.addLayer(vectorGPX);
map.addLayer(vectorGEOJSON);

const marker = new ol.layer.Vector({
  source: new ol.source.Vector({
    features: [
      new ol.Feature({
        geometry: new ol.geom.Point(ol.proj.fromLonLat([23.506092, 60.045847])),
      }),
    ],
  }),
  style: new ol.style.Style({
    image: new ol.style.Icon({
      src: "https://openlayers.org/en/latest/examples/data/icon.png",
      anchor: [0.5, 1],
    }),
  }),
});

map.addLayer(marker);


