/* Only the observed self-thread boundary is characterized. The real USER32
 * call supplies BOOL and last-error, including its failure on self attachment.
 * Cross-thread queue sharing remains guarded; no guest scalar becomes a pointer. */
static void hle_AttachThreadInput(CPU* c) {
    uint32_t from=ARG(0),to=ARG(1),attach=ARG(2),esp=c->r[ESP],caller=rd32(esp);
    DWORD tid=GetCurrentThreadId();BOOL result;
    xrt_event("gui_attach_thread_input_call","\"from\":%u,\"to\":%u,\"attach\":%u,\"esp\":%u,\"return\":%u,\"last_error\":%u",
        from,to,attach,esp,caller,xrt_get_last_error(c));
    if(!c->thread || c->thread->state!=1 || c->thread->host_tid!=tid ||
       c->thread->guest_tid!=tid || from!=tid || to!=tid)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"AttachThreadInput: only the living current guest/host self-thread pair is measured (%u,%u)",from,to);
    begin(c);result=AttachThreadInput(from,to,(BOOL)attach);end(c);
    RET_STD(3,result);
    xrt_event("gui_attach_thread_input_return","\"from\":%u,\"to\":%u,\"attach\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",
        from,to,attach,(unsigned)result,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
