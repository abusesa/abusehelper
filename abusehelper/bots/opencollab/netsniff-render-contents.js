// Example script to use with webshot.py. Returns screenshot, headers
// and file contents of all files involved. Made by combining the
// PhantomJS and CasperJS examples. Requires CasperJS and PhantomJS.
// Maintainer: "Juhani Eronen" <exec@iki.fi>

var BASE64_ENCODE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
var BASE64_DECODE_CHARS = new Array(
	      -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
	      -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
	      -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 62, -1, -1, -1, 63,
	      52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -1, -1, -1, -1, -1, -1,
	      -1,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14,
	      15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, -1, -1, -1, -1,
	      -1, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
	      41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, -1, -1, -1, -1, -1
	      );

function encode(str) {
    var out = "", i = 0, len = str.length, c1, c2, c3;
    while (i < len) {
	c1 = str.charCodeAt(i++) & 0xff;
	if (i === len) {
	    out += BASE64_ENCODE_CHARS.charAt(c1 >> 2);
	    out += BASE64_ENCODE_CHARS.charAt((c1 & 0x3) << 4);
	    out += "==";
	    break;
	}
	c2 = str.charCodeAt(i++);
	if (i === len) {
	    out += BASE64_ENCODE_CHARS.charAt(c1 >> 2);
	    out += BASE64_ENCODE_CHARS.charAt(((c1 & 0x3)<< 4) | ((c2 & 0xF0) >> 4));
	    out += BASE64_ENCODE_CHARS.charAt((c2 & 0xF) << 2);
	    out += "=";
	    break;
	}
	c3 = str.charCodeAt(i++);
	out += BASE64_ENCODE_CHARS.charAt(c1 >> 2);
	out += BASE64_ENCODE_CHARS.charAt(((c1 & 0x3) << 4) | ((c2 & 0xF0) >> 4));
	out += BASE64_ENCODE_CHARS.charAt(((c2 & 0xF) << 2) | ((c3 & 0xC0) >> 6));
	out += BASE64_ENCODE_CHARS.charAt(c3 & 0x3F);
    }
    return out;
};

if (!Date.prototype.toISOString) {
    Date.prototype.toISOString = function () {
        function pad(n) { return n < 10 ? '0' + n : n; }
        function ms(n) { return n < 10 ? '00'+ n : n < 100 ? '0' + n : n }
        return this.getFullYear() + '-' +
            pad(this.getMonth() + 1) + '-' +
            pad(this.getDate()) + 'T' +
            pad(this.getHours()) + ':' +
            pad(this.getMinutes()) + ':' +
            pad(this.getSeconds()) + '.' +
            ms(this.getMilliseconds()) + 'Z';
    }
}

function createHAR(page, address, title, startTime, resources)
{
    var entries = [];

    resources.forEach(function (resource) {
        var request = resource.request,
            startReply = resource.startReply,
            endReply = resource.endReply;

        if (!request || !startReply || !endReply) {
            return;
        }

        entries.push({
            startedDateTime: request.time.toISOString(),
            time: endReply.time - request.time,
            request: {
                method: request.method,
                url: request.url,
                httpVersion: "HTTP/1.1",
                cookies: [],
                headers: request.headers,
                queryString: [],
                headersSize: -1,
                bodySize: -1
            },
            response: {
                status: endReply.status,
                statusText: endReply.statusText,
                httpVersion: "HTTP/1.1",
                cookies: [],
                headers: endReply.headers,
                redirectURL: "",
                headersSize: -1,
                bodySize: startReply.bodySize,
                content: {
                    size: startReply.bodySize,
                    mimeType: endReply.contentType
                }
            },
            cache: {},
            timings: {
                blocked: 0,
                dns: -1,
                connect: -1,
                send: 0,
                wait: startReply.time - request.time,
                receive: endReply.time - startReply.time,
                ssl: -1
            },
            pageref: address
        });
    });

    return {
        log: {
            version: '1.2',
            creator: {
                name: "PhantomJS",
                version: phantom.version.major + '.' + phantom.version.minor +
                    '.' + phantom.version.patch
            },
            pages: [{
                startedDateTime: startTime.toISOString(),
                id: address,
                title: title,
                pageTimings: {
                    onLoad: page.endTime - page.startTime
                }
            }],
            entries: entries
        }
    };
}

var fs = require("fs")
seen = {};
out = "";
resources = [];

var casper = require("casper").create({
    onResourceRequested: function(self, req) {
        resources[req.id] = {
            request: req,
            startReply: null,
            endReply: null
        };
    },
    onResourceReceived: function(self, resource) {
        if (resource.stage === 'start') {
	    resources[resource["id"]].startReply = resource;
        }
        if (resource.stage === 'end') {
	    resources[resource["id"]].endReply = resource;
        }
	if(!(resource["url"] in seen)) {
	    out += resource["url"] + "\n";
	    this.log("Downloading " + resource["url"], "verbose");
	    data = this.base64encode(resource["url"]);
	    if(!data) {
		data = encode(this.getPageContent());
	    }
	    out += data + "\n\n";
	    seen[resource["url"]] = 1;
	}
    },
    viewportSize: {
        width: 1024,
        height: 768
    }
});


var url       = casper.cli.get(0);
var picture   = casper.cli.get(1);
var output    = casper.cli.get(2);
var useragent = casper.cli.get(3);

if (!url || !output || !/\.(png|jpg|pdf)$/i.test(picture)) {
    casper
        .echo("Usage: $ casperjs netsniff-render.js <url> <filename.[jpg|png|pdf]> <output> [user-agent]")
        .exit(1)
    ;
}


casper.start(url).run(function() {
    this.startTime = new Date();
    this.page.settings.localToRemoteUrlAccessEnabled = true;
    if(useragent) {
	this.page.settings.userAgent = useragent;
    }

    this.har = "";

    this.page.render(picture);
     
    this.har = createHAR(this.page, this.getCurrentUrl(), this.getTitle(),
			 this.startTime, resources);
    console.log(JSON.stringify(this.har, undefined, 4));
    fs.write(output, out, "w");
    this.exit();
});
