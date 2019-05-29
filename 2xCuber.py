#!/usr/bin/env python3

from ev3dev2.motor import LargeMotor, OUTPUT_A, OUTPUT_D, SpeedDPS
from pprint import pformat
from subprocess import check_output
from time import sleep
import json
import logging
import os
import signal
import sys
import time

log = logging.getLogger(__name__)

class Cuber2x(object):
    
    hold_cube_pos = 200 #arbitrary need to find
    rotate_speed = 400 #adapt
    flip_speed = 300 #adapt (might need to be slower)


    def __init__(self):
        self.shutdown = False
        self.rotator = LargeMotor(OUTPUT_D)
        self.turntable = LargeMotor(OUTPUT_A)
        
        self.init_motors()
        self.state = ['U','L','F','R','B','D']

        signal.signal(signal.SIGTERM, self.signal_term_handler)
        signal.signal(signal.SIGINT, self.signal_int_handler)

        log.info("Fully initialized")

    def init_motors(self):

        for x in (self.rotator, self.turntable):
            x.reset()

        log.info("Initialize rotator %s" % self.rotator)
        #self.rotator.on(SpeedDPS(-50), block=True)
        self.rotator.off()
        self.rotator.reset()

        log.info("Initialize turntable %s" % self.turntable)
        self.turntable.off()
        self.turntable.reset()

    def shutdown_robot(self):
        log.info('Shutting down')
        self.shutdown = True

        #We are shutting down motors. 
        for x in (self.rotator, self.turntable):
            x.stop_action = 'brake'
            x.off(False)

    def signal_term_handler(self, signal, frame):
        log.error('Caught SIGTERM')

    def signal_int_handler(self, signal, frame):
        log.error('Caught SIGINT')
        self.shutdown_robot()

    def apply_transformation(self, transformation):
        self.state = [self.state[t] for t in transformation]

    def rotate_cube(self, direction, nb):
        current_pos = self.turntable.position
        final_pos = 135 * round((self.turntable.position + (270 * direction * nb)) /135.0)
        log.info("rotate_cube() direction %s, nb %s, current_pos %d final_pos %d" % (direction , nb, current_pos, final_pos))

        if self.rotator.position > 35:
            self.rotator_away()

        self.turntable.on_to_position(SpeedDPS(Cuber2x.rotate_speed), final_pos)

        if nb >= 1:
            for i in range(nb):
                if direction > 0:
                    transformation = [0, 4, 1, 2, 3, 5]
                else:
                    transformation = [0, 2, 3, 4, 1, 5]
                self.apply_transformation(transformation)


    def rotate_cube_1(self):
        self.rotate_cube(1,1)
    
    def rotate_cube_2(self):
        self.rotate_cube(1,2)
    
    def rotate_cube_3(self):
        self.rotate_cube(-1,1)

    def rotate_cube_blocked(self, direction, nb):
    
        #Move the rotator arm down to hold cube in place
        self.rotator_hold_cube()

        #OVERROTATE depends on lot of Cuber2x.rotate_speed
        current_pos = self.turntable.position
        OVERROTATE = 18
        final_pos = int(135 * round((current_pos + (270 * direction * nb)) / 135.0))
        temp_pos = int(final_pos + (OVERROTATE * direction))

        log.info("rotate_cube_blocked() direction %s nb %s, current pos %s, remp pos %s, fial pos %s" % (direction, nb, current_pos, temp_pos, final_pos))

        self.turntable.on_to_position(SpeedDPS(Cuber2x.rotate_speed), temp_pos)
        self.turntable.on_to_position(SpeedDPS(Cuber2x.rotate_speed/4), final_pos)

    def rotate_cube_blocked_1(self):
        self.rotate_cube_blocked(1,1)

    def rotate_cube_blocked_2(self):
        self.rotate_cube_blocked(1,2)
    
    def rotate_cube_blocked_3(self):
        self.rotate_cube_blocked(-1,1)

    def rotator_hold_cube(self, speed=300):
        current_position = self.rotator.position

        print(current_position)
        print(Cuber2x.hold_cube_pos)
        # Push it forward so the cube is always in the same position
        # When we start the flip
        if (current_position <= Cuber2x.hold_cube_pos - 10 or
            current_position >= Cuber2x.hold_cube_pos + 10):
    
            self.rotator.ramp_down_sp=400
            self.rotator.on_to_position(SpeedDPS(speed), Cuber2x.hold_cube_pos)
            log.info("rotated on to position")
            sleep(0.05)



    def rotator_away(self, speed=300):
        """
        Move the rotator arm out of the way
        """
        log.info("rotator_away()")
        self.rotator.ramp_down_sp = 400
        self.rotator.on_to_position(SpeedDPS(speed), 0)

    def flip(self):
        """
        Motors will sometimes stall if you call on on_to_position() multiple times back to back on the same motor. To avoid this we call a 50ms sleep in rotator_hold_cube() and after each on_to_position() below.

        We have to sleep after the 2nd on_to_position() because sometimes flip() is called back to back
        """
        log.info("flip()")


        if self.shutdown:
            return


        self.rotator.on_to_position(SpeedDPS(self.flip_speed), 190)
        self(0.05)

        transformation = [4, 1, 0, 3, 5, 2]
        self.apply_transformation(transformation)

    def scan(self):
        log.info("scan()")
        self.k = 0
        
        #side 0 is scanned

        self.flip()
        #side 4 scanned 

        self.rotate_cube_1()
        
        self.flip()
        #side 1 scanned

        self.flip()
        #side 2 scanned 

        self.flip()
        #side 3 scanned

        self.rotate_cube_2()

        self.flip()
        #side 5 scanned
        
        self.rotate_cube_1()

        self.flip()

        self.flip()

        if self.shutdown:
            return


    def move(self, face_down):
        log.info("move() face_down %s" % face_down)

        position = self.state.index(face_down)
        actions = {
                0: ['flip', 'flip'],
                1: [],
                2: ["rotate_cube_2", "flip"],
                3: ["rotate_cube_1", "flip"],
                4: ["flip"],
                5: ["rotate_cube_3", "flip"]
        }.get(position, None)

        for a in actions:

            if self.shutdown:
                break

            getattr(self, a)()



if __name__== '__main__':
   
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(filename)12s %(levelname)8s: %(message)s')
    log = logging.getLogger(__name__)

    #Color the errors and warnings in red
    logging.addLevelName(logging.ERROR, "\033[91m   %s\033[0m" % logging.getLevelName(logging.ERROR))
    logging.addLevelName(logging.WARNING, "\033[91m %s\033[0m" % logging.getLevelName(logging.WARNING))
    

    x2Cube = Cuber2x()

    try:
        
        #x2Cube.rotator_hold_cube(150)
        x2Cube.rotate_cube(-1,1)
        #x2Cube.rotator_away(150)

        #x2Cube.scan()
        x2Cube.shutdown_robot()

    
    except Exception as e:
        log.exception(e)
        x2Cube.shutdown_robot()
        sys.exit(1)
