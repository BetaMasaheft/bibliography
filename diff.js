//https://stackoverflow.com/questions/3065342/how-do-i-iterate-through-table-rows-and-cells-in-javascript
//https://stackoverflow.com/questions/10539162/using-jquery-to-see-if-a-div-has-a-child-with-a-certain-class
var apiurl = "https://api.zotero.org/groups/358366/items?&tag=";
var style = "&format=bib&style=hiob-ludolf-centre-for-ethiopian-studies";
var styleURL = "&format=bib&style=hiob-ludolf-centre-for-ethiopian-studies-with-url-doi";
var styleNL= "&format=bib&style=hiob-ludolf-centre-for-ethiopian-studies-names-long";
var styleCit = "&format=json&style=hiob-ludolf-centre-for-ethiopian-studies&include=citation";
$(document).ready(function () {
    
    $("#diffstyles").find('tr').each(function () {
        var tag = $(this).find('span.zotID').text()

         var ZotApiCall = apiurl + tag + style
         var ZotApiCallURL = apiurl + tag + styleURL
         var ZotApiCallNL = apiurl + tag + styleNL
         
        var zotRef = $(this).children('td.zotRef0')
        var zotRef1 = $(this).children('td.zotRef1')
        var zotRef2 = $(this).children('td.zotRef2')
        
        $.get(ZotApiCall, function (reference) {
            var text = $(reference).find("div.csl-entry").html()
            zotRef.html(text)
        });
        
        $.get(ZotApiCallURL, function (reference) {
            var text = $(reference).find("div.csl-entry").html()
            zotRef1.html(text)
        });
        
        $.get(ZotApiCallNL, function (reference) {
            var text = $(reference).find("div.csl-entry").html()
            zotRef2.html(text)
        });
        
       
    });
    
$("#examples").find('tr').each(function () {
        var tag = $(this).find('span.zotID').text()

         var ZotApiCall = apiurl + tag + style
        var zotRef = $(this).children('td.zotRef')
        
        $.get(ZotApiCall, function (reference) {
            var text = $(reference).find("div.csl-entry").html()
            zotRef.html(text)
        });
        
        var ZotApiCallCit = apiurl + tag + styleCit
        var zotCit = $(this).children('td.zotCit')
        $.getJSON(ZotApiCallCit, function (citation) {
        console.log(citation["0"].citation)
            var text = citation["0"].citation
            zotCit.html(text)
        });
        
        
    });

});
$(document).ajaxComplete(function () {
$("#examples").find('tr:has(> td)').each(function () {
console.log($(this).html())
            var N = $(this).children('td.Wonnabe').html()
            //console.log(N)
            var O = $(this).children('td.zotRef').html()
            //console.log(O)
            var D = diffString(O.toString(), N.toString());
            //console.log(D)
            $(this).children('td.diff').html(D)
            
        });
        });

/*
 * Javascript Diff Algorithm
 *  By John Resig (http://ejohn.org/)
 *  Modified by Chu Alan "sprite"
 *
 * Released under the MIT license.
 *
 * More Info:
 *  http://ejohn.org/projects/javascript-diff-algorithm/
 */

function escape(s) {
    var n = s;
    n = n.replace(/&/g, "&amp;");
    n = n.replace(/</g, "&lt;");
    n = n.replace(/>/g, "&gt;");
    n = n.replace(/"/g, "&quot;");
    
    return n;
}

function diffString(o, n) {
    o = o.replace(/\s+$/, '');
    n = n.replace(/\s+$/, '');
    
    var out = diff(o == "" ?[]: o.split(/\s+/), n == "" ?[]: n.split(/\s+/));
    var str = "";
    
    var oSpace = o.match(/\s+/g);
    if (oSpace == null) {
        oSpace =[ "\n"];
    } else {
        oSpace.push("\n");
    }
    var nSpace = n.match(/\s+/g);
    if (nSpace == null) {
        nSpace =[ "\n"];
    } else {
        nSpace.push("\n");
    }
    
    if (out.n.length == 0) {
        for (var i = 0; i < out.o.length; i++) {
            str += '<del>' + escape(out.o[i]) + oSpace[i] + "</del>";
        }
    } else {
        if (out.n[0].text == null) {
            for (n = 0; n < out.o.length && out.o[n].text == null; n++) {
                str += '<del>' + escape(out.o[n]) + oSpace[n] + "</del>";
            }
        }
        
        for (var i = 0; i < out.n.length; i++) {
            if (out.n[i].text == null) {
                str += '<ins>' + escape(out.n[i]) + nSpace[i] + "</ins>";
            } else {
                var pre = "";
                
                for (n = out.n[i].row + 1; n < out.o.length && out.o[n].text == null; n++) {
                    pre += '<del>' + escape(out.o[n]) + oSpace[n] + "</del>";
                }
                str += " " + out.n[i].text + nSpace[i] + pre;
            }
        }
    }
    
    return str;
}

function randomColor() {
    return "rgb(" + (Math.random() * 100) + "%, " +
    (Math.random() * 100) + "%, " +
    (Math.random() * 100) + "%)";
}
function diffString2(o, n) {
    o = o.replace(/\s+$/, '');
    n = n.replace(/\s+$/, '');
    
    var out = diff(o == "" ?[]: o.split(/\s+/), n == "" ?[]: n.split(/\s+/));
    
    var oSpace = o.match(/\s+/g);
    if (oSpace == null) {
        oSpace =[ "\n"];
    } else {
        oSpace.push("\n");
    }
    var nSpace = n.match(/\s+/g);
    if (nSpace == null) {
        nSpace =[ "\n"];
    } else {
        nSpace.push("\n");
    }
    
    var os = "";
    var colors = new Array();
    for (var i = 0; i < out.o.length; i++) {
        colors[i] = randomColor();
        
        if (out.o[i].text != null) {
            os += '<span style="background-color: ' + colors[i] + '">' +
            escape(out.o[i].text) + oSpace[i] + "</span>";
        } else {
            os += "<del>" + escape(out.o[i]) + oSpace[i] + "</del>";
        }
    }
    
    var ns = "";
    for (var i = 0; i < out.n.length; i++) {
        if (out.n[i].text != null) {
            ns += '<span style="background-color: ' + colors[out.n[i].row] + '">' +
            escape(out.n[i].text) + nSpace[i] + "</span>";
        } else {
            ns += "<ins>" + escape(out.n[i]) + nSpace[i] + "</ins>";
        }
    }
    
    return {
        o: os, n: ns
    };
}

function diff(o, n) {
    var ns = new Object();
    var os = new Object();
    
    for (var i = 0; i < n.length; i++) {
        if (ns[n[i]] == null)
        ns[n[i]] = {
            rows: new Array(), o: null
        };
        ns[n[i]].rows.push(i);
    }
    
    for (var i = 0; i < o.length; i++) {
        if (os[o[i]] == null)
        os[o[i]] = {
            rows: new Array(), n: null
        };
        os[o[i]].rows.push(i);
    }
    
    for (var i in ns) {
        if (ns[i].rows.length == 1 && typeof (os[i]) != "undefined" && os[i].rows.length == 1) {
            n[ns[i].rows[0]] = {
                text: n[ns[i].rows[0]], row: os[i].rows[0]
            };
            o[os[i].rows[0]] = {
                text: o[os[i].rows[0]], row: ns[i].rows[0]
            };
        }
    }
    
    for (var i = 0; i < n.length - 1; i++) {
        if (n[i].text != null && n[i + 1].text == null && n[i].row + 1 < o.length && o[n[i].row + 1].text == null &&
        n[i + 1] == o[n[i].row + 1]) {
            n[i + 1] = {
                text: n[i + 1], row: n[i].row + 1
            };
            o[n[i].row + 1] = {
                text: o[n[i].row + 1], row: i + 1
            };
        }
    }
    
    for (var i = n.length - 1; i > 0; i--) {
        if (n[i].text != null && n[i -1].text == null && n[i].row > 0 && o[n[i].row - 1].text == null &&
        n[i -1] == o[n[i].row - 1]) {
            n[i -1] = {
                text: n[i -1], row: n[i].row - 1
            };
            o[n[i].row -1] = {
                text: o[n[i].row -1], row: i - 1
            };
        }
    }
    
    return {
        o: o, n: n
    };
}