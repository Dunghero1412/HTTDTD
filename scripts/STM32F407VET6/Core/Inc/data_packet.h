#ifndef DATA_PACKET_H
#define DATA_PACKET_H

#include <stdint.h>
#include "main.h"
#include "tim2_capture.h"

/* Buffer đủ cho 4 dòng: "[A, 0xXXXXXXXX]\n" × 4 */
/*#define PACKET_BUF_SIZE  80U*/
#define PACKET_BUF_SIZE  20U

typedef struct {
    uint8_t  buf[PACKET_BUF_SIZE];
    uint16_t len;
} Packet_t;

/*
 * Tạo chuỗi dạng:
 *   [A, 0x1A2B3C4D]
 *   [B, 0x00FFAABB]
 *   [C, 0x...]
 *   [D, 0x...]
 */
void Packet_Build(const volatile CaptureData_t *cap, Packet_t *out);

#endif
