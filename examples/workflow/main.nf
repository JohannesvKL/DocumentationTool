// @param input Input file path.
// @param message Message printed with the input path.
params.input = 'data.txt'
params.message = 'hello'
workflow {
    log.info "${params.message}: ${params.input}"
}
