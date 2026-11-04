echo "Get the latest version"
curl -o ./data/versions.json http://localhost:23119/api/groups/358366/items/top?format=versions

echo "Get all the top items in JSON format"
curl -o ./data/all-top-items.json http://localhost:23119/api/groups/358366/items/top

echo "Get all the top items in TEI format"
curl -o ./data/all-top-items.xml http://localhost:23119/api/groups/358366/items/top?format=tei

echo "Get all the top items in CSLJSON format"
curl -o ./data/all-top-items.csljson http://localhost:23119/api/groups/358366/items/top?format=csljson

echo "Process all the top items"
time python3 ./modules/process-all-top-items/process-all-top-items.py


echo "Get the latest top items in JSON format"
curl -o ./public/latest-top-items.json https://api.zotero.org/groups/358366/items/top?since=13774

# jq -s 'map(INDEX(.key)) | add | [.[]]' ./data/a.json ./data/b.json > ./public/merged.json