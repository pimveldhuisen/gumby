library(ggplot2)
library(igraph)

genesis_id_base64 = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
half_sign_hash_base64 = "MTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTE=="

add_block_vertex_to_graph <- function(block){
    if (block["Previous_Hash"] == genesis_id_base64) {
        print("Found Origin Block")
        graph<<-graph+vertex(sprintf(block["Block_Hash"]), color="darkolivegreen4")
     } else {
        #Normal block
        graph<<-graph+vertex(sprintf(block["Block_Hash"]), color="darkgoldenrod1")
        print("Add vertex: " )
        print(sprintf(block["Block_Hash"]))
    }
}

add_block_edges_to_graph <- function(block){
    tryCatch(
        {
            graph<<-graph+edge(sprintf(block["Block_Hash"]),sprintf((block["Previous_Hash"])))
            graph<<-graph+edge(sprintf(block["Block_Hash"]),sprintf(get_hash_from_pk_sn(block["Linked_Public_key"],block["Linked_Sequence_Number"])))

         # graph<<-graph+edge(sprintf(block["Block_Hash"]),sprintf(get_requester_hash_from_any_hash(block["Block_Hash"])))
         # graph<<-graph+edge(sprintf(block["Block_Hash"]),sprintf(get_requester_hash_from_any_hash(block["Block_Hash"])))

         #   if (block["Previous_Hash_Responder"] == half_sign_hash_base64 && block["Previous_Hash_Requester"] == genesis_id_base64) {
         #       # Found Half-Signed Origin Block
         #    } else if (block["Previous_Hash_Responder"] == half_sign_hash_base64) {#or block.previous_hash_requester == GENESIS_ID:
         #       # Half-Signed Block
         #       graph<<-graph+edge(sprintf(block["Hash_Requester"]),sprintf(get_requester_hash_from_any_hash(block["Previous_Hash_Requester"])))
         #   } else if (block["Previous_Hash_Responder"] == genesis_id_base64 && block["Previous_Hash_Requester"] == genesis_id_base64) {
         #       # Double Origin Block
         #   } else if (block["Previous_Hash_Requester"] == genesis_id_base64) {
         #       # Found Requester Origin Block
         #       graph<<-graph+edge(sprintf(block["Hash_Requester"]),sprintf(get_requester_hash_from_any_hash(block["Previous_Hash_Responder"])))
         #   } else if (block["Previous_Hash_Responder"] == genesis_id_base64) {
         #       # Found Responder Origin Block
         #       graph<<-graph+edge(sprintf(block["Hash_Requester"]),sprintf(get_requester_hash_from_any_hash(block["Previous_Hash_Requester"])))
         #    } else {
         #       #Normal block
         #       graph<<-graph+edge(sprintf(block["Hash_Requester"]),sprintf(get_requester_hash_from_any_hash(block["Previous_Hash_Responder"])))
         #       graph<<-graph+edge(sprintf(block["Hash_Requester"]),sprintf(get_requester_hash_from_any_hash(block["Previous_Hash_Requester"])))
        #    }
        },
        warning = function(w) {warning(w)},
        error = function(e)
            {
                warning(e)
                warning(block["Block_Hash"])
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

get_hash_from_pk_sn <- function(pk, sn){
    block = data[data$Public_Key == pk  & data$Sequence_Number == sn]
    return(as.character(block["Block_Hash"]))
}

multichain_file = "multichain.dat"

if(file.exists("output/multichain.dat")) {
    multichain_file = "output/multichain.dat"
} else if (file.exists("output/multichain/multichain.dat")){
    multichain_file = "output/multichain/multichain.dat"
}

if (!file.exists(multichain_file)) {
    print("Unable to find multichain data file")
    multichain_file = "null"
}

Hilbert <- function(level=5, x=0, y=0, xi=1, xj=0, yi=0, yj=1) {
    if (level <= 0) {
        return(c(x + (xi + yi)/2, y + (xj + yj)/2))
    } else {
        return(rbind(
            Hilbert(level-1, x,           y,           yi/2, yj/2,  xi/2,  xj/2),
            Hilbert(level-1, x+xi/2,      y+xj/2 ,     xi/2, xj/2,  yi/2,  yj/2),
            Hilbert(level-1, x+xi/2+yi/2, y+xj/2+yj/2, xi/2, xj/2,  yi/2,  yj/2),
            Hilbert(level-1, x+xi/2+yi,   y+xj/2+yj,  -yi/2,-yj/2, -xi/2, -xj/2)
        ))
    }
}

if(multichain_file != "null") {
    print("Generating Multichain graph")
    data <- read.table(multichain_file, header = TRUE, sep =" ", row.names = NULL)
    print("1")
    both <- levels(data$Public_Key)
    print("2")
    positions <- head(Hilbert(level=ceiling(log(nrow(data))/log(4))), nrow(data))
    print("3")
    data <- cbind(public_key=as.numeric(factor(data$Public_Key, levels=both)), data)
    print("4")
    data <- data[ order(data[,"Insert_Time"]), ]

    graph <- make_empty_graph()

    apply(data, 1, add_block_vertex_to_graph)
    apply(data, 1, add_block_edges_to_graph)

    svg('output/multichain.svg', width = 25, height = 25)
    plot(graph, layout=positions, vertex.size=2, edge.color="black", vertex.label=NA, vertex.color= V(graph)$color, edge.label=NA)

    svg('output/multichain_labels.svg', width = 25, height = 25)
    plot(graph, layout=positions, vertex.size=2, edge.color="black", vertex.color= V(graph)$color, edge.label=NA)

    svg('output/multichain_edge_labels.svg', width = 250, height = 250)
    plot(graph, layout=positions, vertex.size=0.2, edge.color="black", vertex.label=NA, vertex.color= V(graph)$color)

    png('output/multichain.png', width = 800, height = 800)
    plot(graph, layout=positions, vertex.size=2, edge.color="black", vertex.label=NA, vertex.color= V(graph)$color, edge.label=NA)

    png('output/multichain_labels.png', width = 800, height = 800)
    plot(graph, layout=positions, vertex.size=2, edge.color="black", vertex.color= V(graph)$color, edge.label=NA)

    png('output/multichain_edge_labels.png', width = 1600, height = 1600)
    plot(graph, layout=positions, vertex.size=0.1, edge.color="black", vertex.label=NA, vertex.color= V(graph)$color)
}

warnings()
