import logging
import os
import time

from RPi import GPIO

import cc1101
from cc1101.options import (
    _TransceiveMode,
)
from cc1101.addresses import (
    ConfigurationRegisterAddress,
    FIFORegisterAddress,
    PatableAddress,
    StatusRegisterAddress,
    StrobeAddress,
)


logging.basicConfig(level=logging.INFO)

_GDO0_PIN = 18  # GPIO24
GDO2 = 22
CSN = 12

GPIO.setmode(GPIO.BOARD)
GPIO.setup(_GDO0_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(GDO2, GPIO.IN)

# you know what i just found out at 3am? that the NON REALTIME OPERATING SYSTEM LINUX cannot sleep for 1uS! WOW! WHO WOULD'VE KNOWN!!!!
#usleep = lambda x: time.sleep(x/1000000.0)
usleep = lambda ms: 1 if 1 > ms else [x for x in range(ms*3)]

def deleteTrailingNull(bits):
    _bytes = []
    for x in range(0, len(bits), 8):
        _bytes.append(bits[x:8+x])

class pCC1101():
    def __init__(self, spi_bus=0, spi_chip_select=0, retries=5):

        self.success = False
        self.err = None
        for x in range(retries):
            try:
                self.trs = cc1101.CC1101(spi_bus=spi_bus, spi_chip_select=spi_chip_select).__enter__()
                print("[CC1101] successful init")
                self.success = True
                break
            except Exception as e:
                self.err = e
                print(e)
                print("[CC1101] executing cc1101 CSN reset")
                self._csnRst()
                print("[CC1101] finished with CSN reset")

        if not self.success:
            raise self.err
        
        self.snval = 0
        self.currentFreq = 303.81e6

        self._setDefaults()

        self.setupRawTransmission()

        self.adjustOOKSensitivity(0, 0xC2)

        self.rawTransmit2("101010", delayms=10)

        self.mode = "tx"

        #time.sleep(0.5)

        pass
    
    def _setDefaults(self):
        #self.setRxBW(812.0)
        #self.currentFreq = 303.81e6

        #self.trs._command_strobe(StrobeAddress.SIDLE)

        self.setRxBW(650.0)

        self.setCCMode(0)
        self.trs.set_base_frequency_hertz(self.currentFreq)

        """
        abcd = self.trs.get_base_frequency_hertz()

        print("-*"* 30)
        print(self.currentFreq)
        print(abcd)
        print(f"base_frequency={(abcd / 1e6):.2f}MHz",)
        print("-*"* 30)
        """

        #self.trs._write_burst(ConfigurationRegisterAddress.MDMCFG1,  [0x02]);
        #self.trs._write_burst(ConfigurationRegisterAddress.MDMCFG0,  [0xF8]);
        #self.trs._write_burst(ConfigurationRegisterAddress.DEVIATN,  [0x47]);
        self.trs._write_burst(ConfigurationRegisterAddress.FREND1,   [0x56]);
        #self.trs._write_burst(ConfigurationRegisterAddress.MCSM0 ,   [0x18]);
        #self.trs._write_burst(ConfigurationRegisterAddress.FOCCFG,   [0x16]);
        #self.trs._write_burst(ConfigurationRegisterAddress.BSCFG,    [0x1C]);
        self.trs._write_burst(0x1B, [0xC7]);
        self.trs._write_burst(0x1C, [0x00]);
        self.trs._write_burst(0x1D, [0xB2]);
        #self.trs._write_burst(ConfigurationRegisterAddress.FSCAL3,   [0xE9]);
        #self.trs._write_burst(ConfigurationRegisterAddress.FSCAL2,   [0x2A]);
        #self.trs._write_burst(ConfigurationRegisterAddress.FSCAL1,   [0x00]);
        #self.trs._write_burst(ConfigurationRegisterAddress.FSCAL0,   [0x1F]);
        #self.trs._write_burst(ConfigurationRegisterAddress.FSTEST,   [0x59]);
        #self.trs._write_burst(ConfigurationRegisterAddress.TEST2,    [0x81]);
        #self.trs._write_burst(ConfigurationRegisterAddress.TEST1,    [0x35]);
        #self.trs._write_burst(ConfigurationRegisterAddress.TEST0,    [0x09]);
        #self.trs._write_burst(ConfigurationRegisterAddress.PKTCTRL1, [0x04]);
        #self.trs._write_burst(ConfigurationRegisterAddress.ADDR,     [0x00]);
        #self.trs._write_burst(ConfigurationRegisterAddress.PKTLEN,   [0x00]);
    
    def close(self):
        GPIO.output(_GDO0_PIN, 1)
        self.rst()
        self.trs._command_strobe(StrobeAddress.SIDLE)

    def csn(self, value):
        return
        if value:
            GPIO.cleanup(CSN)
            print("csn up")
        else:
            print('csn down')
            GPIO.setup(CSN, GPIO.IN)
            time.sleep(0.5)
            GPIO.setup(CSN, GPIO.OUT)
            GPIO.output(CSN, 1)

    def setFreq(self, val, rst=True):

        #self.setRxBW(812.50)
        #self.setCCMode(0)

        self.currentFreq = eval("{}e6".format(val))

        print(self.currentFreq)

        if rst:
            self._setDefaults() # TODO: figure out why the fuck 303.91mhz turns into 1.04mhz in the cc1101 # i figured it out its cause it wasn't in SIDLE

    def _csnRst(self):
        csn = 12

        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(csn, GPIO.IN)

        time.sleep(1)

        GPIO.setup(csn, GPIO.OUT)
        GPIO.output(csn, 1)
        time.sleep(0.5)

        GPIO.cleanup(csn)

    def rawTransmit(self, bt:bytes, delayms=10) -> None:
        """
        Turn hexadecimal bytes (```\x0F```) into binary, and send bits to the CC1101.

        e.g. ```rawTransmit(b"\x02\x0F\xFF")```
        """
        
        for byte in bt:
            bits = bin(byte)[2:]

            for bit in bits:
                if bit == "1":
                    GPIO.output(_GDO0_PIN, GPIO.HIGH)
                else:
                    GPIO.output(_GDO0_PIN, GPIO.LOW)

                usleep(delayms)

        GPIO.output(_GDO0_PIN, self.snval)

        #self._command_strobe(StrobeAddress.SIDLE)

    def rawTransmit2(self, lbt, delayms=1, inverse=False) -> None:
        """
        Play bits through the CC1101 via a list.

        e.g. ```rawTransmit2([0,1,1,0,1])```
        """
        #with self.trs.asynchronous_transmission():

        bits = [int(x) for x in lbt]
        output = GPIO.output
        gdoPin = _GDO0_PIN

        for bit in bits:
            output(gdoPin, bit)

            if delayms != 0:
                usleep(delayms)

        output(gdoPin, self.snval)

    def rawRecv(self, bits:int, uslp=1) -> list:
        """
        Recieve data through the GDO2 pin.
        This sends no data to the CC1101.

        Returns a list of bits.
        """
        recvd = []

        for x in range(bits*8):
            a = GPIO.input(GDO2)
            if a:
                recvd.append(1)
            else:
                recvd.append(0)
            usleep(uslp)

        return recvd
    
    def rawRecv2(self, uslp=1):
        """
        Recieve data through the GDO2 pin.
        This sends no data to the CC1101.

        This method waits for a high bit, then starts yielding the data.
        """
        zerosInARow = 0
        sending = False

        while True:
            a = GPIO.input(GDO2)

            if not sending:
                if a:
                    sending = True
                    yield 1
                else:
                    yield -1
            else:
                if zerosInARow == 200:
                    break

                if a:
                    zerosInARow = 0
                    yield 1
                else:
                    zerosInARow += 1
                    yield 0

            usleep(uslp)

    def rawRecv3(self, uslp=1):
        """
        Recieve data through the GDO2 pin.
        This sends no data to the CC1101.

        This method yields every bit. Nothing special.
        """

        inp = GPIO.input
        gdo = GDO2

        while 1:
            yield inp(gdo)

            if uslp != 0:
                usleep(uslp)

    def flipperRecv(self):
        """
        Recieve data through the GDO2 pin, outputting it in flipper zero's RAW format.
        """
        raise NotImplementedError("use flipperconv class")

    def split_PKTCTRL0(self):
        global pc0CRC_EN, pc0LenConf, pc0WDATA, pc0PktForm
        calc = self.trs._read_status_register(ConfigurationRegisterAddress.PKTCTRL0)

        pc0WDATA = 0
        pc0PktForm = 0
        pc0CRC_EN = 0
        pc0LenConf = 0

        while True:
            if calc >= 64:
                calc -= 64
                pc0WDATA += 64

            elif calc >= 16:
                calc -= 16
                pc0PktForm += 16

            elif calc >= 4:
                calc -= 4
                pc0CRC_EN += 4

            else:
                pc0LenConf = calc
                break

    def Split_MDMCFG4(self):
        global m4RxBw, m4DaRa
        """
        void ELECHOUSE_CC1101::Split_MDMCFG4(void){
            int calc = SpiReadStatus(16);
            m4RxBw = 0;
            m4DaRa = 0;
            for (bool i = 0; i==0;){
                if (calc >= 64){calc-=64; m4RxBw+=64;}
                else if (calc >= 16){calc -= 16; m4RxBw+=16;}
                else{m4DaRa = calc; i=1;}
            }
        }
        """

        calc = self.trs._read_status_register(16)

        m4RxBw = 0;
        m4DaRa = 0;

        while True:
            if calc >= 64:
                calc -= 64 
                m4RxBw += 64

            elif calc >= 16:
                calc -= 16
                m4RxBw += 16
            else:
                m4DaRa = calc
                break
    
    def _setGDO0(self, val):
        GPIO.output(_GDO0_PIN, val)

    def _setGDO2(self, val):
        GPIO.setup(GDO2, GPIO.OUT, initial=GPIO.LOW)
        GPIO.output(GDO2, val)

    def setRxBW(self, f):
        global m4RxBw
        """
        Set the bandwidth for the CC1101's RX.
        Default is 812.50
        """
        """
        void ELECHOUSE_CC1101::setRxBW(float f){
            Split_MDMCFG4();
            int s1 = 3;
            int s2 = 3;
            for (int i = 0; i<3; i++){
                if (f > 101.5625){f/=2; s1--;}
                else{i=3;}
            }
            for (int i = 0; i<3; i++){
                if (f > 58.1){f/=1.25; s2--;}
                else{i=3;}
            }
            s1 *= 64;
            s2 *= 16;
            m4RxBw = s1 + s2;
            SpiWriteReg(16,m4RxBw+m4DaRa);
        }
        """

        self.Split_MDMCFG4()

        s1 = 3
        s2 = 3

        for x in range(3):
            if f > 101.5625:
                f = f/2
                s1 -= 1
            else:
                break

        for x in range(3):
            if f> 58.1:
                f = f/1.25
                s2 -= 1
            else:
                break

        s1 = s1*64
        s2 = s2*16

        m4RxBw = s1 + s2
        self.trs._write_burst(16,[m4RxBw+m4DaRa])

    def rst(self):
        self._setDefaults()
        print('[+] set cc1101 defaults')

        self.setupRawTransmission()
        print('[+] set cc1101 to TX')

        #self.adjustOOKSensitivity(0, 0x51)
        #print('[+] set cc1101 OOK to 0x51')

        self.rawTransmit2("101010", delayms=100)
        print('[+] transmitted some example bits')

        self.mode = "tx"

    def revertTransceiver(self) -> None:
        """
        Revert the CC1101 back to normal settings, without actually resetting the chip.
        """

        """
        SpiWriteReg(CC1101_IOCFG2,      0x0B);
        SpiWriteReg(CC1101_IOCFG0,      0x06);
        SpiWriteReg(CC1101_PKTCTRL0,    0x05);
        SpiWriteReg(CC1101_MDMCFG3,     0xF8);
        SpiWriteReg(CC1101_MDMCFG4,11+m4RxBw);
        """

        #self.setCCMode(0)

        # end of ccmode


        self.trs._command_strobe(StrobeAddress.SIDLE)
        self.trs._command_strobe(StrobeAddress.SRX)
        #self.trs._set_transceive_mode(_TransceiveMode.ASYNCHRONOUS_SERIAL)
        #self.trs._command_strobe(StrobeAddress.SFTX)
        #self.trs._command_strobe(StrobeAddress.SFRX)
        #self.trs._command_strobe(StrobeAddress.SRX)

    def setCCMode(self, v):

        if v==1:
            self.trs._write_burst(cc1101.ConfigurationRegisterAddress.IOCFG2, [0x0B])
            self.trs._write_burst(cc1101.ConfigurationRegisterAddress.IOCFG0, [0x06])
            self.trs._write_burst(cc1101.ConfigurationRegisterAddress.PKTCTRL0, [0x05])
            self.trs._write_burst(cc1101.ConfigurationRegisterAddress.MDMCFG3, [0x05])
            self.trs._write_burst(cc1101.ConfigurationRegisterAddress.MDMCFG4, [11+m4RxBw])
        else:
            self.trs._write_burst(cc1101.ConfigurationRegisterAddress.IOCFG2, [0x0D])
            self.trs._write_burst(cc1101.ConfigurationRegisterAddress.IOCFG0, [0x0D])
            self.trs._write_burst(cc1101.ConfigurationRegisterAddress.PKTCTRL0, [0x32])
            self.trs._write_burst(cc1101.ConfigurationRegisterAddress.MDMCFG3, [0x93])
            self.trs._write_burst(cc1101.ConfigurationRegisterAddress.MDMCFG4, [7+m4RxBw])

        self.trs._set_modulation_format(0b011)
        
    def setupRawTransmission(self, output_power=0xCB) -> None:
        """
        Sets up the CC1101 to transmit.
        """
        #self.setRxBW(812.50)

        """
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.IOCFG2, [0x0B])
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.IOCFG0, [0x06])
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.PKTCTRL0, [0x05])
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.MDMCFG3, [0xF8])
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.MDMCFG4, [11+m4RxBw])
        """

        #self.setRxBW(812.50)

        # set cc mode

        """
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.IOCFG2, [0x0D])
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.IOCFG0, [0x0D])
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.PKTCTRL0, [0x32])
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.MDMCFG3, [0x93])
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.MDMCFG4, [7+m4RxBw])

        self.trs._set_modulation_format(0b011)
        """

        #self.setCCMode(0)

        # end of setting cc mode

        
        #v = 3
        #split_PKTCTRL0(trans)
        #pc0PktForm = v*16;
        #trans._write_burst(ConfigurationRegisterAddress.PKTCTRL0, [pc0WDATA+pc0PktForm+pc0CRC_EN+pc0LenConf]);

        #self.trs._set_modulation_format(0b011)
        #self.trs.set_output_power((0, 0xCB))  # OOK modulation: (off, on)

        #self.trs._command_strobe(StrobeAddress.SFRX)

        self.setCCMode(0)
        
        self.trs._set_transceive_mode(_TransceiveMode.ASYNCHRONOUS_SERIAL) # setPktFormat(3)
        
        self.trs._command_strobe(StrobeAddress.SIDLE)
        self.trs._command_strobe(StrobeAddress.STX)

        self.mode = "tx"
        #self.setFreq(self.currentFreq)
        self.adjustOOKSensitivity(0, 0xC2)
        #self.trs._command_strobe(StrobeAddress.SIDLE)

    def adjustOOKSensitivity(self, zero, one) -> None:
        """
        Adjusts the logic levels of 0 and 1 for OOK modulation. This can also increase TX power.
        Increase "one" if you're recieving too much static, decrease if you aren't recieving anything.

        See "Table 39: Optimum PATABLE Settings for Various Output Power Levels [...]"
        and section "24 Output Power Programming".

        Recommended value is 0xC6.
        """
        assert 0xFF >= zero and 0xFF >= one and zero >= 0 and one >= 1 # sanity check

        self.trs.set_output_power((zero, one))

    def setupRawRecieve(self) -> None:
        """
        Set the CC1101 to recieve raw data through the GDO2 pin.
        If no data is recieved but you know data is being transmitted, adjust the OOK sensitivity using ```self.adjustOOKSensitivity```.
        """
        global pc0CRC_EN, pc0LenConf, pc0WDATA, pc0PktForm, m4RxBw


        """
        SpiWriteReg(CC1101_IOCFG2,      0x0D);
        SpiWriteReg(CC1101_IOCFG0,      0x0D);
        SpiWriteReg(CC1101_PKTCTRL0,    0x32);
        SpiWriteReg(CC1101_MDMCFG3,     0x93);
        SpiWriteReg(CC1101_MDMCFG4, 7+m4RxBw);
        """

        #self.setRxBW(812.50)

        # set cc mode

        """
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.IOCFG2, [0x0D])
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.IOCFG0, [0x0D])
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.PKTCTRL0, [0x32])
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.MDMCFG3, [0x93])
        self.trs._write_burst(cc1101.ConfigurationRegisterAddress.MDMCFG4, [7+m4RxBw])

        self.trs._set_modulation_format(0b011)
        """

        #self.setCCMode(0)

        # end of setting cc mode

        
        #v = 3
        #split_PKTCTRL0(trans)
        #pc0PktForm = v*16;
        #trans._write_burst(ConfigurationRegisterAddress.PKTCTRL0, [pc0WDATA+pc0PktForm+pc0CRC_EN+pc0LenConf]);

        #self.trs._set_modulation_format(0b011)
        #self.trs.set_output_power((0, 0xCB))  # OOK modulation: (off, on)

        #self.trs._command_strobe(StrobeAddress.SFTX)
        self.setCCMode(0)
        
        self.trs._set_transceive_mode(_TransceiveMode.ASYNCHRONOUS_SERIAL) # setPktFormat(3)
        
        self.trs._command_strobe(StrobeAddress.SIDLE)
        self.trs._command_strobe(StrobeAddress.SRX)
        #self.setFreq(self.currentFreq)

        self.mode = "rx"

    def setPktFormat(self, val):
        if val == "async":
            self.trs._set_transceive_mode(_TransceiveMode.ASYNCHRONOUS_SERIAL)
        elif val == "fifo":
            self.trs._set_transceive_mode(_TransceiveMode.FIFO)

if __name__ == "__main__":
    with cc1101.CC1101(spi_bus=1) as transceiver:
        transceiver.set_base_frequency_hertz(303.91e6)
        #transceiver.set_symbol_rate_baud(300)
        print("starting transmission")

        # lower value = more
        transceiver.set_output_power((0, 0x0D))  # OOK modulation: (off, on)
        #transceiver._enable_receive_mode()

        # TESTING
        # TESTING
        
        setupRawRecieve(transceiver)

        bt = [x for x in "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000111110000000000000000000000000000000000000000000000000000000000001110000011111110000000000110000000000111000000000111000000000111000000000011100000111111100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000111000011111111100000000111100000000111100000000111100000000111100000111111110000000011110000000011110000000011111000000001110000000001111000011111111000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001111000011111111000000000111000000000111000000000111100000000111100001111111100000000111100000000011110000000011110000000011110000000011110000111111111000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000011110000111111110000000001110000000001111000000001111000000001111000011111111000000000111100000000111100000000111100000000011110000000011110000111111110000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000111100001111111100000000011110000000011110000000011110000000011110000111111111000000001111000000001111000000001111000000000111000000000111100001111111100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001111100001111111100000000111100000000111110000000011110000000011110000111111110000000011110000000001111000000001111000000001111000000001111000011111111100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000011111000011111111000000001111000000001111000000000111100000000111100001111111100000000111100000000111100000000111100000000011110000000011110000111111110000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000111100001111111100000000011110000000011110000000011110000000001111000011111111000000001111000000001111000000000111100000001111000000000111100001111111100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000111100001111111100000000111100000000111100000000011110000000011110000111111110000000011110000000001111000000001111000000001111000000001111100011111111100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001111000011111111000000001111000000000111000000000111100000000111100001111111100000000011100000000011110000000011110000000001111000000001111000011111111000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000011111000111111111000000001111000000001111000000001111000000000111100001111111100000000111100000000111100000000111110000000111110000000011110000000011110000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001111100001111111100000000111100000000111100000000111100000000011110000111111110000000011110000000011110000000001110000000001111000000000111000000000111100000000000000000000000000000000000000000000000000000000000000000000000000"]
        time.sleep(1)

        os.system('clear')


        print(''.join([str(x) for x in bt]))
        input("...")

        print("TRANASMIT")
        setupRawTransmission(transceiver)
        rawTransmit2(transceiver, bt, delayms=1)
        print("FINISH")

        time.sleep(0.25)

        revertTransceiver(transceiver)

        #transceiver._reset()
        transceiver.unlock_spi_device()
        transceiver._spi.close()
        time.sleep(0.25)
#"""