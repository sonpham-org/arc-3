"""a102 Impedance Steps -- grade intermediate stiffness to transmit a pulse."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LAB,MEDIUM,STIFF,SOFT,PULSE,REFLECT,TRANSMIT,GATE,BAD=14,8,9,12,10,11,4,13,6,15
LEVELS=[
 {"name":"Adjust Layer","seq":(1,)},{"name":"Select Layer","seq":(2,)},
 {"name":"Test Pulse","seq":(1,3)},{"name":"Grade Interface","seq":(1,2,1,3,4)},
 {"name":"Reduce Reflection","seq":(2,1,3,2,1,4,3)},{"name":"Impedance Steps","seq":(1,2,1,3,4,2,1,3,4,3)},
]
def advance(s,a):
 layers,cursor,energy,reflected,gate,pulses,history,snapshot=s;l=list(layers)
 if a==1:l[cursor]=(l[cursor]+1)%5;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%5;history=(history+(2,))[-8:]
 elif a==3:
  jumps=abs(0-l[0])+sum(abs(l[i]-l[i+1]) for i in range(4))+abs(l[-1]-4);reflected=(reflected+jumps)%9;energy=max(0,12-jumps);pulses=(pulses+1)%7;history=(history+(3,))[-8:]
 elif a==4:gate=(gate+int(energy>=7))%6;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(l),cursor,energy,reflected,gate,pulses,history)
 return tuple(l),cursor,energy,reflected,gate,pulses,history,snapshot
for x in LEVELS:
 s=((0,4,1,3,4),0,0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB
  for i,v in enumerate(g.layers):x=8+i*9;f[16:48,x:x+8]=MEDIUM;f[44-v*6:48,x+1:x+7]=STIFF if v>=3 else SOFT
  x=8+g.cursor*9;f[10:14,x:x+8]=PULSE
  f[51:55,8:8+g.energy*4]=TRANSMIT;f[55:58,8:8+g.reflected*4]=REFLECT;f[16:48,54:59]=GATE if g.gate else MEDIUM
  if g.bad:f[1:4,18:46]=BAD
  return f
class A102(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a102",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.layers,self.cursor,self.energy,self.reflected,self.gate,self.pulses,self.history,self.snapshot=((0,4,1,3,4),0,0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.layers,self.cursor,self.energy,self.reflected,self.gate,self.pulses,self.history,self.snapshot=advance((self.layers,self.cursor,self.energy,self.reflected,self.gate,self.pulses,self.history,self.snapshot),a)
  elif a==6:
   if (self.layers,self.cursor,self.energy,self.reflected,self.gate,self.pulses,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
