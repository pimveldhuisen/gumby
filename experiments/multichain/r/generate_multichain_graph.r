library(ggplot2)
library(igraph)

genesis_id_base64 = "MDAwMDAwMDAwMDAwMDAwMDAwMDA="
half_sign_hash_base64 = "MDAwMDAwMDAwMDAwMDAwMDAwMDE="

add_block_vertex_to_graph <- function(block){
    if (block["Previous_Hash_Responder"] == half_sign_hash_base64 && block["Previous_Hash_Requester"] == genesis_id_base64) {
        print("Found Half-Signed Origin Block")
        graph<<-graph+vertex(sprintf(block["Block_ID"]), color="purple")
    } else if (block["Previous_Hash_Responder"] == half_sign_hash_base64) {
        print("Found Half-Signed Block")
        graph<<-graph+vertex(sprintf(block["Block_ID"]), color="red")
    } else if (block["Previous_Hash_Responder"] == genesis_id_base64 && block["Previous_Hash_Requester"] == genesis_id_base64) {
        print("Found Double Origin Block") # Both requester and responder have no previous blocks
        graph<<-graph+vertex(sprintf(block["Block_ID"]), color="darkolivegreen3")
    } else if (block["Previous_Hash_Requester"] == genesis_id_base64) {
        print("Found Requester Origin Block")
        graph<<-graph+vertex(sprintf(block["Block_ID"]), color="darkolivegreen4")
    } else if (block["Previous_Hash_Responder"] == genesis_id_base64) {
        print("Found Responder Origin Block")
        graph<<-graph+vertex(sprintf(block["Block_ID"]), color="darkolivegreen4")
     } else {
        #Normal block
        graph<<-graph+vertex(sprintf(block["Block_ID"]), color="darkgoldenrod1")
    }
}

add_block_edges_to_graph <- function(block){
    tryCatch(
        {
            if (block["Previous_Hash_Responder"] == half_sign_hash_base64 && block["Previous_Hash_Requester"] == genesis_id_base64) {
                # Found Half-Signed Origin Block
             } else if (block["Previous_Hash_Responder"] == half_sign_hash_base64) {#or block.previous_hash_requester == GENESIS_ID:
                # Half-Signed Block
                graph<<-graph+edge(sprintf(block["Block_ID"]),sprintf(block["Previous_Hash_Requester"]))
            } else if (block["Previous_Hash_Responder"] == genesis_id_base64 && block["Previous_Hash_Requester"] == genesis_id_base64) {
                # Double Origin Block
            } else if (block["Previous_Hash_Requester"] == genesis_id_base64) {
                # Found Requester Origin Block
                graph<<-graph+edge(sprintf(block["Block_ID"]),sprintf(block["Previous_Hash_Responder"]))
            } else if (block["Previous_Hash_Responder"] == genesis_id_base64) {
                # Found Responder Origin Block
                graph<<-graph+edge(sprintf(block["Block_ID"]),sprintf(block["Previous_Hash_Requester"]))
             } else {
                #Normal block
                graph<<-graph+edge(sprintf(block["Block_ID"]),sprintf(block["Previous_Hash_Responder"]))
                graph<<-graph+edge(sprintf(block["Block_ID"]),sprintf(block["Previous_Hash_Requester"]))
            }
        },
        warning = function(w) {warning(w)},
        error = function(e)
            {
                warning(e)
                warning(block["Block_ID"])
            },
        finally ={}
    )
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

    graph <- make_empty_graph()

    apply(data, 1, add_block_vertex_to_graph)
    apply(data, 1, add_block_edges_to_graph)

    svg('output/multichain.svg', width = 25, height = 25)
    plot(graph, layout=layout.kamada.kawai, vertex.size=2, edge.color="black", vertex.label=NA, vertex.color= V(graph)$color)

    svg('output/multichain_labels.svg', width = 25, height = 25)
    plot(graph, layout=layout.kamada.kawai, vertex.size=2, edge.color="black", vertex.color= V(graph)$color)

    png('output/multichain.png', width = 800, height = 800)
    plot(graph, layout=layout.kamada.kawai, vertex.size=2, edge.color="black", vertex.label=NA, vertex.color= V(graph)$color)

    png('output/multichain_labels.png', width = 800, height = 800)
    plot(graph, layout=layout.kamada.kawai, vertex.size=2, edge.color="black", vertex.color= V(graph)$color)
}

