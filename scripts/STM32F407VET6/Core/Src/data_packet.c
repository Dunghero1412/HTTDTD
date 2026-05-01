#include "data_packet.h"
#include <string.h>
#include <stdio.h>

/* Label cho 4 sensor */
/*static const char sensor_label[NUM_SENSORS] = {'A', 'B', 'C', 'D'};*/

/* ────────────────────────────────────────────────────
 *  Packet_Build
 *  Output format:
 *    [A, 0x1A2B3C4D]\n
 *    [B, 0x00FFAABB]\n
 *    [C, 0xDEADBEEF]\n
 *    [D, 0x00001234]\n
 * ──────────────────────────────────────────────────── */
/*void Packet_Build(const volatile CaptureData_t *cap, Packet_t *out) {
    out->len = 0;
    memset(out->buf, 0, PACKET_BUF_SIZE);

    for (uint8_t i = 0; i < NUM_SENSORS; i++) { */
        /* Mỗi dòng tối đa: "[A, 0xDEADBEEF]\n" = 17 ký tự */
/*        char line[20];
        int n = snprintf(line, sizeof(line),
                         "[%c, 0x%08lX]\n",
                         sensor_label[i],
                         (unsigned long)cap->timestamp[i]);

        if (n > 0 && (out->len + (uint16_t)n) < PACKET_BUF_SIZE) {
            memcpy(&out->buf[out->len], line, (uint16_t)n);
            out->len += (uint16_t)n;
        }
    }
}
*/
/*
#include "data_packet.h"
#include <string.h>
*/
static const char sensor_id[NUM_SENSORS] = {'A', 'B', 'C', 'D'};

void Packet_Build(const volatile CaptureData_t *cap, Packet_t *out) {
    out->len = PACKET_BUF_SIZE;
    uint8_t *p = out->buf;

    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        uint32_t ts = cap->timestamp[i];
        *p++ = (uint8_t)sensor_id[i];
        *p++ = (uint8_t)(ts >> 24);
        *p++ = (uint8_t)(ts >> 16);
        *p++ = (uint8_t)(ts >> 8);
        *p++ = (uint8_t)(ts);
    }
}
