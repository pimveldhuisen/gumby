library(ggplot2)
library(igraph)

genesis_id_base64 = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
half_sign_hash_base64 = "MTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTE=="

add_block_vertex_to_graph <- function(block){
    if (block["Previous_Hash_Responder"] == half_sign_hash_base64 && block["Previous_Hash_Requester"] == genesis_id_base64) {
        print("Found Half-Signed Origin Block")
        graph<<-graph+vertex(sprintf(block["Hash_Requester"]), color="purple")
    } else if (block["Previous_Hash_Responder"] == half_sign_hash_base64) {
        print("Found Half-Signed Block")
        graph<<-graph+vertex(sprintf(block["Hash_Requester"]), color="red")
    } else if (block["Previous_Hash_Responder"] == genesis_id_base64 && block["Previous_Hash_Requester"] == genesis_id_base64) {
        print("Found Double Origin Block") # Both requester and responder have no previous blocks
        graph<<-graph+vertex(sprintf(block["Hash_Requester"]), color="darkolivegreen3")
    } else if (block["Previous_Hash_Requester"] == genesis_id_base64) {
        print("Found Requester Origin Block")
        graph<<-graph+vertex(sprintf(block["Hash_Requester"]), color="darkolivegreen4")
    } else if (block["Previous_Hash_Responder"] == genesis_id_base64) {
        print("Found Responder Origin Block")
        graph<<-graph+vertex(sprintf(block["Hash_Requester"]), color="darkolivegreen4")
     } else {
        #Normal block
        graph<<-graph+vertex(sprintf(block["Hash_Requester"]), color="darkgoldenrod1")
        print("Add vertex: " )
        print(sprintf(block["Hash_Requester"]))
    }
}

add_block_edges_to_graph <- function(block){
    tryCatch(
        {
            if (block["Previous_Hash_Responder"] == half_sign_hash_base64 && block["Previous_Hash_Requester"] == genesis_id_base64) {
                # Found Half-Signed Origin Block
             } else if (block["Previous_Hash_Responder"] == half_sign_hash_base64) {#or block.previous_hash_requester == GENESIS_ID:
                # Half-Signed Block
                graph<<-graph+edge(sprintf(block["Hash_Requester"]),sprintf(get_requester_hash_from_any_hash(block["Previous_Hash_Requester"])), label=sprintf(block["id_req"]))
            } else if (block["Previous_Hash_Responder"] == genesis_id_base64 && block["Previous_Hash_Requester"] == genesis_id_base64) {
                # Double Origin Block
            } else if (block["Previous_Hash_Requester"] == genesis_id_base64) {
                # Found Requester Origin Block
                graph<<-graph+edge(sprintf(block["Hash_Requester"]),sprintf(get_requester_hash_from_any_hash(block["Previous_Hash_Responder"])), label=sprintf(block["id_resp"]))
            } else if (block["Previous_Hash_Responder"] == genesis_id_base64) {
                # Found Responder Origin Block
                graph<<-graph+edge(sprintf(block["Hash_Requester"]),sprintf(get_requester_hash_from_any_hash(block["Previous_Hash_Requester"])), label=sprintf(block["id_req"]))
             } else {
                #Normal block
                graph<<-graph+edge(sprintf(block["Hash_Requester"]),sprintf(get_requester_hash_from_any_hash(block["Previous_Hash_Responder"])), label=sprintf(block["id_resp"]))
                graph<<-graph+edge(sprintf(block["Hash_Requester"]),sprintf(get_requester_hash_from_any_hash(block["Previous_Hash_Requester"])), label=sprintf(block["id_req"]))
            }
        },
        warning = function(w) {warning(w)},
        error = function(e)
            {
                warning(e)
                warning(block["Hash_Requester"])
            },
        finally ={}
    )
}

get_requester_hash_from_any_hash <- function(hash){
 requester = data[data[,"Hash_Requester"]==hash,]
 dimensions = dim(requester)
 if (dimensions[1] == 1) {
    return(as.character(requester[1,"Hash_Requester"]))
  } else {
    responder = data[data[,"Hash_Responder"]==hash,]
    return(as.character(responder[1,"Hash_Requester"]))
  }
}

multichain_file = "null"

if(file.exists("output/multichain.dat")) {
    multichain_file = "output/multichain.dat"
} else if (file.exists("output/multichain/multichain.dat")){
    multichain_file = "output/multichain/multichain.dat"
}

if(multichain_file != "null") {
    print("Generating Multichain graph")
    data <- read.table(multichain_file, header = TRUE, sep =" ", row.names = NULL)
    both <- union(levels(data$Public_Key_Requester), levels(data$Public_Key_Responder))
    data <- cbind(id_req=as.numeric(factor(data$Public_Key_Requester, levels=both)), id_resp=as.numeric(factor(data$Public_Key_Responder, levels=both)), data)

    graph <- make_empty_graph()

    apply(data, 1, add_block_vertex_to_graph)
    apply(data, 1, add_block_edges_to_graph)

    svg('output/multichain.svg', width = 25, height = 25)
    plot(graph, layout=layout.kamada.kawai, vertex.size=2, edge.color="black", vertex.label=NA, vertex.color= V(graph)$color, edge.label=NA)

    svg('output/multichain_labels.svg', width = 25, height = 25)
    plot(graph, layout=layout.kamada.kawai, vertex.size=2, edge.color="black", vertex.color= V(graph)$color, edge.label=NA)

    svg('output/multichain_edge_labels.svg', width = 25, height = 25)
    plot(graph, layout=layout.kamada.kawai, vertex.size=2, edge.color="black", vertex.label=NA, vertex.color= V(graph)$color)

    png('output/multichain.png', width = 800, height = 800)
    plot(graph, layout=layout.kamada.kawai, vertex.size=2, edge.color="black", vertex.label=NA, vertex.color= V(graph)$color, edge.label=NA)

    png('output/multichain_labels.png', width = 800, height = 800)
    plot(graph, layout=layout.kamada.kawai, vertex.size=2, edge.color="black", vertex.color= V(graph)$color, edge.label=NA)

    png('output/multichain_edge_labels.png', width = 800, height = 800)
    plot(graph, layout=layout.kamada.kawai, vertex.size=2, edge.color="black", vertex.label=NA, vertex.color= V(graph)$color)
}

