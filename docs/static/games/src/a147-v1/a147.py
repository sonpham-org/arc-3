"""a147 Common Cause -- intervene upstream to distinguish confounding from a direct link."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LAB,SENSOR,LAMP_A,LAMP_B,SHIELD,TRIGGER,LINK,COMMON,DIRECT=14,8,12,10,13,6,11,9,4,7
BAD=15
LEVELS=[
 {"name":"Shield Sensor","seq":(1,)},{"name":"Select Sensor","seq":(2,)},
 {"name":"Send Trigger","seq":(3,1)},{"name":"Test Correlation","seq":(1,2,3,4,2)},
 {"name":"Reveal Common Cause","seq":(1,3,2,1,4,3,2)},{"name":"Common Cause","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 shields,cursor,trigger,lamps,common,direct,history,snapshot=s
 if a==1:shields^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%3;history=(history+(2,))[-8:]
 elif a==3:
  trigger=(trigger+1)%4;upstream=int(not (shields&1));lamps=(upstream&(trigger%2),upstream&(trigger%2));history=(history+(3,))[-8:]
 elif a==4:common=int(lamps[0]==lamps[1] and bool(shields&1));direct=int(lamps[0]!=lamps[1]);history=(history+(4,))[-8:]
 elif a==5:snapshot=(shields,cursor,trigger,lamps,common,direct,history)
 return shields,cursor,trigger,lamps,common,direct,history,snapshot
for q in LEVELS:
 s=(0,0,0,(0,0),0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB
  for i,x in enumerate((12,30,48)):
   f[11:22,x-5:x+6]=SENSOR
   if (g.shields>>i)&1:f[8:25,x-8:x-5]=SHIELD
   if i==g.cursor:f[6:9,x-7:x+8]=TRIGGER
  f[30:46,14:28]=LAMP_A if g.lamps[0] else DIRECT;f[30:46,36:50]=LAMP_B if g.lamps[1] else DIRECT;f[22:33,29:35]=LINK
  f[54:58,8:32]=COMMON if g.common else DIRECT;f[7:10,8:8+g.trigger*9]=TRIGGER
  if g.bad:f[1:4,18:46]=BAD
  return f
class A147(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a147",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.shields,self.cursor,self.trigger,self.lamps,self.common,self.direct,self.history,self.snapshot=(0,0,0,(0,0),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.shields,self.cursor,self.trigger,self.lamps,self.common,self.direct,self.history,self.snapshot=advance((self.shields,self.cursor,self.trigger,self.lamps,self.common,self.direct,self.history,self.snapshot),a)
  elif a==6:
   if (self.shields,self.cursor,self.trigger,self.lamps,self.common,self.direct,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
