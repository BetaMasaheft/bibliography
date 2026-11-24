xquery version "1.0";

(:~
 : Reindex EthioStudies after deploy so @tag range picks up existing
 : citations when upgrading a package that previously had no xconf.
 :)
import module namespace xmldb = "http://exist-db.org/xquery/xmldb";

declare variable $home external;
declare variable $dir external;
declare variable $target external;

xmldb:reindex($target)
