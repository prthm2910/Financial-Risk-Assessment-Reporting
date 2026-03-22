import streamlit as st
from streamlit.components.v1 import html
import colorsys

def generate_distinct_colors(n):
    colors = []
    for i in range(n):
        hue = i * (360.0 / n)
        lightness = 50 + (i % 3) * 10
        saturation = 90 - (i % 2) * 20
        rgb = colorsys.hls_to_rgb(hue/360.0, lightness/100.0, saturation/100.0)
        colors.append(f"rgb({int(rgb[0]*255)},{int(rgb[1]*255)},{int(rgb[2]*255)})")
    return colors

def get_graph(graphData : dict):
    d3_graph_code = """<!DOCTYPE html>
<html>
<head>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/dompurify@2.4.0/dist/purify.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        #graph-wrapper {
            width: 100%;
            height: 650px;
            position: relative;
            border-radius: 8px;
            overflow: hidden;
            background-color: transparent;
        }
        #graph-container {
            width: 100%;
            height: 650px;
            background-color: transparent;
        }
        #node-info-container {
            width: calc(100% - 32px);
            height: 200px;
            padding: 15px;
            margin: 0 15px;
            background-color: #0e1117;
            color: white;
            border: 1px solid white;
            border-radius: 8px;
            position: absolute;
            bottom: 0;
            left: 0;
            overflow-y: auto;
            transition: all 0.3s ease;
            box-sizing: border-box;
        }
        .node circle {
            stroke: var(--node-stroke);
            stroke-width: 2px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .node circle:hover {
            r: 14px;
            stroke-width: 3px;
            stroke: var(--node-stroke-hover);
        }
        .link {
            stroke: rgba(200, 200, 200, 0.8);
            stroke-opacity: 0.9;
            stroke-width: 1.5px;
        }
        .node text {
            font: 13px sans-serif;
            font-weight: 600;
            pointer-events: none;
            fill: var(--text-color);
            text-shadow: 0 1px 2px var(--text-shadow), 
                        1px 0 2px var(--text-shadow), 
                        -1px 0 2px var(--text-shadow), 
                        0 -1px 2px var(--text-shadow);
            paint-order: stroke;
            stroke: var(--text-outline);
            stroke-width: 3px;
            stroke-opacity: 0.7;
        }
        #node-info a {
            color: #4dabf7;
            text-decoration: underline;
        }
        #node-info strong {
            color: white;
        }
        #node-info em {
            color: #f8f9fa;
        }
    </style>
</head>
<body>
    <div id="graph-wrapper">
        <div id="graph-container"></div>
        <div id="node-info-container">
            <div id="node-info-default" style="color: white;">Click on any node to view details</div>
            <div id="node-info" style="display: none; color: white;"></div>
        </div>
    </div>

    <script>
        const style = getComputedStyle(document.body);
        const streamlitColors = {
            background: style.getPropertyValue('--background-color').trim() || 'rgba(255, 255, 255, 0.7)',
            text: style.getPropertyValue('--text-color').trim() || '#31333F',
            border: style.getPropertyValue('--border-color').trim() || 'rgba(49, 51, 63, 0.2)',
            shadow: style.getPropertyValue('--shadow-color').trim() || 'rgba(0, 0, 0, 0.1)'
        };

        document.documentElement.style.setProperty('--background-color', streamlitColors.background);
        document.documentElement.style.setProperty('--text-color', streamlitColors.text);
        document.documentElement.style.setProperty('--border-color', streamlitColors.border);
        document.documentElement.style.setProperty('--box-shadow', `0 2px 10px ${streamlitColors.shadow}`);
        document.documentElement.style.setProperty('--node-stroke', streamlitColors.background);
        document.documentElement.style.setProperty('--node-stroke-hover', streamlitColors.text);
        document.documentElement.style.setProperty('--text-shadow', streamlitColors.background);
        document.documentElement.style.setProperty('--text-outline', streamlitColors.background);

        const graphData = {{graphData}};
        const nodeColors = {{NODE_COLORS}};
        const width = document.getElementById('graph-container').clientWidth;
        const height = 550;

        const svg = d3.select("#graph-container")
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .style("background-color", "transparent");

        const g = svg.append("g");

        const simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.links).id(d => d.id).distance(130))
            .force("charge", d3.forceManyBody().strength(-400))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(45));

        const link = g.append("g")
            .selectAll("line")
            .data(graphData.links)
            .enter().append("line")
            .attr("class", "link")
            .attr("stroke-width", d => Math.sqrt(d.value || 1));

        const node = g.append("g")
            .selectAll(".node")
            .data(graphData.nodes)
            .enter().append("g")
            .attr("class", "node")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));

        node.append("circle")
            .attr("r", 14)
            .attr("fill", (d, i) => nodeColors[i % nodeColors.length])
            .on("click", function(event, d) {
                document.getElementById('node-info-default').style.display = 'none';
                const infoDiv = document.getElementById('node-info');
                infoDiv.style.display = 'block';

                const rawHTML = marked.parse(d.description);
                infoDiv.innerHTML = DOMPurify.sanitize(rawHTML);

                d3.select(this)
                    .transition()
                    .duration(200)
                    .attr("r", 18)
                    .attr("stroke-width", 4);
            });

        node.append("text")
            .attr("dx", 18)
            .attr("dy", 5)
            .text(d => d.name)
            .style("font-size", "13px")
            .style("font-weight", "bold");

        simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("transform", d => `translate(${Math.max(25, Math.min(width - 25, d.x))},${Math.max(25, Math.min(height - 25, d.y))})`);
        });

        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }

        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }

        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }

        window.addEventListener('resize', function() {
            const newWidth = document.getElementById('graph-container').clientWidth;
            svg.attr("width", newWidth);
            simulation.force("center", d3.forceCenter(newWidth / 2, height / 2));
            simulation.alpha(0.3).restart();
        });
    </script>
</body>
</html>
"""
    

    st.title(" Risk Category Inter-Dependency Visualization")
    node_colors = generate_distinct_colors(20)
    final_code = d3_graph_code.replace("{{NODE_COLORS}}", str(node_colors)).replace("{{graphData}}", str(graphData))
    return html(final_code, height=700)
