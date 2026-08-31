"""q797 Spectrum Rhythm -- interrupt a prism packet macro at a relational phase event."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PRISM,PACKET,FAST,SLOW,RELATION,GOAL,BAD=8,10,11,14,6,12,9,13,15
LEVELS=[{"name":"Packet Beat","seq":(1,)},{"name":"Split Pane","seq":(2,1)},{"name":"Scaled Interval","seq":(3,1,2)},{"name":"Relation Sample","seq":(4,2,1,3)},{"name":"Interrupt Window","seq":(2,3,1,4,2,1)},{"name":"Spectrum Rhythm","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 packet,pane,fast,slow,routine,relations,interrupt=s
 if a==1:packet=(packet+1+pane)%8;fast=(fast+1)%4;slow=(slow+int(fast==0))%5;routine=routine+(1,)
 elif a==2:packet=(packet+2+slow)%8;pane=(pane+1)%4;fast=(fast+2)%4;routine=routine+(2,)
 elif a==3:fast=(fast+1)%4;slow=(slow+2)%5;pane=(pane+fast+slow)%4;routine=routine+(3,)
 elif a==4:relations=relations+(((packet-pane)%8,fast,slow,len(routine)%4),)
 elif a==5:interrupt=(packet,pane,fast,slow,routine[-5:],relations[-3:])
 return packet,pane,fast,slow,routine,relations,interrupt
for x in LEVELS:
 s=(0,0,0,0,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GALLERY
  for i in range(8):x=8+(i%4)*12;y=8+(i//4)*13;f[y:y+9,x:x+9]=PRISM;f[y+2:y+7,x+2:x+7]=PACKET if i==g.packet else RELATION
  for i,(r,a,b,_) in enumerate(g.relations[-3:]):x=8+i*15;f[36:42,x:x+11]=RELATION;f[43:46,x:x+2+a*2]=FAST;f[47:49,x:x+2+b*2]=SLOW
  f[51:54,8:8+g.fast*11+8]=FAST;f[56:59,8:8+g.slow*9+7]=SLOW
  if g.interrupt:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q797(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q797",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.packet=self.pane=self.fast=self.slow=0;self.routine=self.relations=();self.interrupt=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.packet,self.pane,self.fast,self.slow,self.routine,self.relations,self.interrupt=advance((self.packet,self.pane,self.fast,self.slow,self.routine,self.relations,self.interrupt),a)
  elif a==6:
   if (self.packet,self.pane,self.fast,self.slow,self.routine,self.relations,self.interrupt)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
