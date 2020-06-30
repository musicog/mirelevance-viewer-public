// websocket variable (initialized in $(document).ready
var socket;

var strata = ["Content", "Processing", "Engineering", "Interface", "Cognitive", "Affective", "Situational", "Social Context", "Cultural Context"];
var heatCellWidth = 82;
var heatCellHeight = 83;
var heatmap, ctx, parentOffset, fudgeX, fudgeY; // to be initialised in $(document).ready
var img = new Image();

function heatmapRelativePosition(x, y)  { 
        // position 0,0 at the top-left corner of the top-left heatmap cell:
        x -= fudgeX;
        y -= fudgeY;
        cellx = Math.floor(x/heatCellWidth);
        celly = Math.floor(y/heatCellHeight);
        return {"x":cellx, "y": celly};

}

function displayStratComps(stratComps) { 
    var stratCompsHTML = ""
    for (sCTuple in stratComps) { 
        var tupleID = stratComps[sCTuple][1]["tupleID"].join("_");
        var freq = stratComps[sCTuple][1]["freq"];
        var numStudies = stratComps[sCTuple][1]["numStudies"];
        var findings = stratComps[sCTuple][1]["findings"].join("_");
        var sC = stratComps[sCTuple][1]["stratComps"];

        // sort sC's according to stratum
        sC = sC.sort(function(a, b) { 
            return strata.indexOf(a["stratum"]) - strata.indexOf(b["stratum"]);
        })

        sCTuple = ""
        for (s in sC) { 
            sCTuple += '<span class="stratCompDescriptor" title="' + sC[s]["hint"] + 
                        '">' + sC[s]["stratum"] + ": " + sC[s]["description"] + "</span>";
        }
        
        stratCompsHTML +=
            '<div class="stratCompTuple" id="' + tupleID + '" data-findings="' + findings + '" onclick="showFindings(event, this)"><span class="stratCompTupleFreq">' + numStudies + " studies, " + freq + " findings: </span>" + sCTuple + "<span class='expand'>+</span><div class='findings'></div></div>";
    }
    $("#stratComps").html(stratCompsHTML);
}

function showFindings(e, element) { 
    var stateIndicator = $(element).children(".expand");
    if ($(stateIndicator).hasClass("closed")) { 
        // user wants to reopen the previously closed div
        $(stateIndicator).removeClass("closed");
        $(stateIndicator).addClass("open");
        $(stateIndicator).html("-");
        $(element).children(".findings").css("display", "block");
    }
    else if($(stateIndicator).hasClass("open")) {
        // user wants to hide the findings for this stratCompTuple 
        $(stateIndicator).html("+");
        $(stateIndicator).removeClass("open");
        $(stateIndicator).addClass("closed");
        $(element).children(".findings").css("display", "none");
    }
    else { 
        // we haven't loaded the findings yet, so request them and open the div:
        socket.emit('showFindingsRequest', {
            "tupleID": $(element).attr("id"),
            "findings": $(element).attr("data-findings").split("_")
        });
        $(stateIndicator).html("-");
        $(stateIndicator).addClass("open");
    }
}


$(document).ready(function() { 
    // set up websocket
    socket = io.connect('http://' + document.domain + ':' + location.port, { 'path': '/relevance-socketio' });
    socket.on('connect', function() { 
        socket.emit('clientConnectionEvent', 'Client connected.');
        console.log('Connected to server.');
    });
    socket.on('stratCompRequestHandled', function(sC) { 
        $("#loading").html("");
        displayStratComps(sC);
    });

    socket.on('showFindingsRequestHandled', function(message) { 
        var findingsHTML = "";
        for (var f in message["findings"]) { 
            findingsHTML += 
            "<div class='finding'>" + 
            "<div class='findingid'><span class='header'>FindingID:</span> " + message["findings"][f]["findingid"] + "</div>" +
            "<div class='fdescription'><span class='header'>Description:</span> " + message["findings"][f]["f.description"] +"</div>" +
                    "<div class='sid'><span class='header'>StudyID:</span> " + message["findings"][f]["s.id"] + "</div>" +
                    "<div class='sdescription'><span class='header'>Study description:</span> " + message["findings"][f]["s.description"]+ "</div>" +
                    "<div class='smethodology'><span class='header'>Study methodology:</span> " + message["findings"][f]["s.methodology"] +"</div>" +
                    "<div class='ssampleframe'><span class='header'>Study sample frame:</span> " + message["findings"][f]["s.sampleframe"] +"</div>" +
                    "<div class='ssamplesize'><span class='header'>Study sample size:</span> " + message["findings"][f]["s.samplesize"] +"</div>" +
                  //  "<div class='slimitations'><span class='header'>Study limitations:</span> " + message["findings"][f]["s.limitations"] +"</div>"+ 
                   // "<div class='scomments'><span class='header'>Study comments:</span> " + message["findings"][f]["s.comments"] + "</div>" +
                   // "<div class='sreliability'><span class='header'>Study reliability:</span> " + message["findings"][f]["s.reliability"]+ "</div>"+
                    "<div class='atitle'><span class='header'>Article title:</span> " + message["findings"][f]["a.title"]+ "</div>"+
                    "<div class='aauthors'><span class='header'>Article authors:</span> " + message["findings"][f]["a.authors"]+ "</div>"+
                    "<div class='ayear'><span class='header'>Year of publication:</span> " + message["findings"][f]["a.year"]+ "</div>"+
                    "<div class='ajournal'><span class='header'>Article journal:</span> " + message["findings"][f]["a.journal"]+ "</div>"+
                    "<div class='aid'><span class='header'>Article ID:</span> " + message["findings"][f]["a.id"]+ "</div>"+
                    "<div class='scholar'><span class='header'>Scholar:</span>" + 
                    "<span class='scholarlink'>" + 
                    "<a href='http://scholar.google.ca/scholar?q="  + 
                        encodeURI(message["findings"][f]["a.title"])  + 
                        "' target='_blank'>Search for article</a></span></div>" + 
                    "</div>";
                }
        $('#' + message["tupleID"]).children(".findings").html(findingsHTML);
        $('.scholarlink').click(function(e) { e.stopPropagation() });
    });
        
    heatmap = document.getElementById("heatmap");
    ctx = heatmap.getContext("2d");
    parentOffset = $("#heatmap").parent().offset();
    fudgeX = 109 + parentOffset.left;
    fudgeY = parentOffset.top;

    img.addEventListener("load", function() { 
        ctx.drawImage(img, 0, 0);
    }, false);
    img.src = "/relevance-static/heatmap.png";
    

    $("#heatmap").click(function(e) { 
        var cellPos = heatmapRelativePosition(e.pageX, e.pageY)
        var cellx = cellPos["x"];
        var celly = cellPos["y"];

        if(cellx >= 0 && cellx < strata.length && celly >= 0 && celly < strata.length) {
            $("#selected_left").html(strata[cellx]);
            $("#selected_right").html(strata[strata.length-1-celly]);
            
            $("#loading").html(">> Loading stratum component descriptors list...");
	    $("#stratComps").html("");
            socket.emit('stratCompRequest',[strata[cellx], strata[strata.length-1-celly]] );

        }

    })
    
    $("#heatmap").mousemove(function(e) { 
        // refresh the image
        ctx.drawImage(img, 0, 0);
        // draw a highlighting rectangle around the appropriate cell
        var cellPos = heatmapRelativePosition(e.pageX, e.pageY)
        var cellx = cellPos["x"];
        var celly = cellPos["y"];

        if(cellx >= 0 && cellx < strata.length && celly >= 0 && celly < strata.length) {
            // we are on the grid
            ctx.beginPath();
            ctx.fillStyle="rgba(225, 150,150, 0.5";
            ctx.fillRect(fudgeX + (cellx*heatCellWidth), fudgeY + (celly*heatCellHeight), heatCellWidth, heatCellHeight);
            ctx.strokeStyle="brown";
            ctx.rect(fudgeX + (cellx*heatCellWidth), fudgeY + (celly*heatCellHeight), heatCellWidth, heatCellHeight);
            ctx.stroke();
            //console.log("Parent offsets: ", parentOffset.left, ", ",parentOffset.top, " Mouse at: page - ", e.pageX, ",", e.pageY,", canvas: ", x, ",", y,", cellx: ", cellx, "celly: ", celly, "on labels: ", strata[cellx], ", ",strata[strata.length-1-celly]);
        }
    })
})
