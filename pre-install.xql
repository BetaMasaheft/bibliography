xquery version "1.0";

(:~
 : Store collection.xconf into /db/system/config{$target} before package
 : resources are loaded, so @tag range indexes apply on install.
 : Same pattern as BetMas lists/parser packages.
 :)
import module namespace xmldb = "http://exist-db.org/xquery/xmldb";

(: Set by repo:deploy :)
declare variable $home external;
declare variable $dir external;
declare variable $target external;

declare function local:mkcol-recursive ($collection, $components) {
	if (exists($components)) then
		let $newColl := concat($collection, "/", $components[1])
		return (
			xmldb:create-collection($collection, $components[1]),
			local:mkcol-recursive($newColl, subsequence($components, 2))
		)
	else (
	)
};

declare function local:mkcol ($collection, $path) {
	local:mkcol-recursive($collection, tokenize($path, "/"))
};

local:mkcol("/db/system/config", $target),
xmldb:store-files-from-pattern(concat("/system/config", $target), $dir, "*.xconf")
