"""a103 Resonant Cavity -- test and retune geometry-selected input rhythms."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,HALL,CAVITY,WALL,RHYTHM,RESONANCE,NEIGHBOR,PULSE,AMPLIFY,BAD=15,8,9,4,12,14,10,11,13,6
LEVELS=[
 {"name":"Pulse Rhythm","seq":(1,)},{"name":"Change Rhythm","seq":(2,)},
 {"name":"Find Resonance","seq":(1,2,1)},{"name":"Retune Wall","seq":(1,3,2,1,4)},
 {"name":"Avoid Neighbor","seq":(2,1,3,2,1,4,1)},{"name":"Resonant Cavity","seq":(1,2,1,3,4,2,1,3,2,1)},
]
def advance(s,a):
 geometry,rhythm,response,neighbors,pulses,history,snapshot=s
 if a==1:response=(response+(5-abs((rhythm%5)-(geometry%5))))%9;neighbors=(neighbors+int(rhythm==(geometry+1)%5))%6;pulses=(pulses+1)%8;history=(history+(1,))[-8:]
 elif a==2:rhythm=1+rhythm%5;history=(history+(2,))[-8:]
 elif a==3:geometry=1+geometry%6;response=0;history=(history+(3,))[-8:]
 elif a==4:response=(response+geometry*rhythm)%9;history=(history+(4,))[-8:]
 elif a==5:snapshot=(geometry,rhythm,response,neighbors,pulses,history)
 return geometry,rhythm,response,neighbors,pulses,history,snapshot
for x in LEVELS:
 s=(3,1,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HALL;left=18-g.geometry;right=46+g.geometry;f[13:50,left:left+5]=WALL;f[13:50,right:right+5]=WALL;f[18:45,left+5:right]=CAVITY
  for i in range(g.rhythm):f[27-i*3:32+i*3,29+i*2:32+i*2]=RHYTHM
  f[8:12,8:8+g.response*5]=RESONANCE;f[52:56,8:8+g.neighbors*7]=NEIGHBOR
  for i in range(g.pulses):f[55:58,36+i*3:39+i*3]=PULSE
  f[22:38,52:58]=AMPLIFY
  if g.bad:f[1:4,18:46]=BAD
  return f
class A103(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a103",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.geometry,self.rhythm,self.response,self.neighbors,self.pulses,self.history,self.snapshot=(3,1,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.geometry,self.rhythm,self.response,self.neighbors,self.pulses,self.history,self.snapshot=advance((self.geometry,self.rhythm,self.response,self.neighbors,self.pulses,self.history,self.snapshot),a)
  elif a==6:
   if (self.geometry,self.rhythm,self.response,self.neighbors,self.pulses,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
