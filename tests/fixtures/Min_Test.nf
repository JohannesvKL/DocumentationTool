#!/usr/bin/env nextflow
nextflow.enable.dsl=2

params.message = params.message ?: 'Hello'
params.count   = params.count   ?: 3

process sayHello {
    input:
    val msg
    val n

    output:
    stdout

    script:
    """
    echo "Message: ${msg}"
    echo "Repeating ${n} times:"
    for i in \$(seq 1 ${n}); do echo "${msg} (\$i)"; done
    """
}

workflow {
    msg_ch = Channel.value(params.message)
    count_ch = Channel.value(params.count)
    sayHello(msg_ch, count_ch).collectFile(name: 'hello.txt')
}

workflow.onComplete {
    if (workflow.success) {
        println "Workflow complete!"
    } else {
        println "Workflow failed: ${workflow.errorMessage}"
    }
}
