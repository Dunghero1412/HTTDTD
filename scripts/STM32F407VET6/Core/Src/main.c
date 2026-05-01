#include "main.h"
#include "gpio_control.h"
#include "tim2_capture.h"
#include "spi_comm.h"
#include "data_packet.h"

volatile SystemState_t g_system_state = STATE_IDLE;
volatile uint32_t g_wait_timeout = 0;

int main(void) {
    SystemClock_Config();
    GPIO_Control_Init();
    TIM2_Capture_Init();
    SPI2_Init();

    Packet_t pkt;

    while (1) {
        switch (g_system_state) {

        case STATE_IDLE:
            if (RunTrg_IsHigh()) {
                TIM2_Capture_Start();
                g_system_state = STATE_CAPTURING;
            }
            break;

        case STATE_CAPTURING:
            /* Kiểm tra PB1 bị kéo Low → reset toàn bộ */
            if (!RunTrg_IsHigh()) {
                TIM2_Capture_Stop();
                DataReady_Clear();
                g_system_state = STATE_IDLE;
                break;
            }
            /* IRQ sẽ set state → PACKAGING khi đủ 4 sensor */
            break;

/*        case STATE_PACKAGING:
            Packet_Build(&g_capture, &pkt);
            SPI2_Transmit(pkt.buf, pkt.len);
            DataReady_Set();              // báo RPi
            g_system_state = STATE_WAITING;
            break;

        case STATE_WAITING:
            /* RPi kéo CS / handshake → DATA_READY về Low */
            /* (hoặc polling PB0 phản hồi từ RPi) */
/*            if (!DataReady_IsHigh()) {    // RPi đã nhận
                TIM2_Capture_Start();     // capture lại
                g_system_state = STATE_CAPTURING;
*/
	case STATE_PACKAGING:
	    Packet_Build(&g_capture, &pkt);
	    SPI2_Transmit(pkt.buf, pkt.len);
	    DataReady_Set();
	    g_system_state = STATE_WAITING;
	    g_wait_timeout = 10;   // timeout 10ms (đếm ngược trong vòng lặp)
	    break;

	case STATE_WAITING:
	    /* Giảm timeout mỗi lần lặp (giả sử vòng lặp chính ~1ms) */
	    if (g_wait_timeout > 0) {
	        g_wait_timeout--;
	    } else {
	        DataReady_Clear();
	        if (RunTrg_IsHigh()) {
	            TIM2_Capture_Start();
	            g_system_state = STATE_CAPTURING;
	        } else {
	            g_system_state = STATE_IDLE;
	        }
	    }
	    /* Kiểm tra nút bấm tắt bất kỳ lúc nào */
	    if (!RunTrg_IsHigh()) {
	        DataReady_Clear();
	        TIM2_Capture_Stop();
	        g_system_state = STATE_IDLE;
	    }
	    break;
        }
            /* Vẫn kiểm tra PB1 */
/*            if (!RunTrg_IsHigh()) {
                TIM2_Capture_Stop();
                DataReady_Clear();
                g_system_state = STATE_IDLE;
            }
            break;
        }*/
    }
}

/* ── IRQ Handler ────────────────────────────────── */
/*void TIM2_IRQHandler(void) {*/
/*    TIM2_IRQHandler_Impl();*/
    /* Khi đủ 4 sensor trong Impl → set STATE_PACKAGING */
/*}*/
