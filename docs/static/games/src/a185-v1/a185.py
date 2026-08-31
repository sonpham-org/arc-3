"""a185 Missing Packet -- recover visible erasures from redundancy across cycles."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CHANNEL,PACKET_A,PACKET_B,ERASURE,RECONSTRUCT,CURSOR,CYCLE,CORRECT,ERROR=6,8,12,14,7,10,13,11,4,9
BAD=15
MESSAGE=(0,1,1,0,1,0,0,1)
LEVELS=[
 {"name":"Fill Erasure","seq":(1,)},{"name":"Select Packet","seq":(2,)},
 {"name":"Change Cycle","seq":(3,1)},{"name":"Compare Redundancy","seq":(1,2,3,4,2)},
 {"name":"Recover Packet","seq":(1,3,2,1,4,3,2)},{"name":"Missing Packet","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 guesses,cursor,cycle,correct,errors,history,snapshot=s;g=list(guesses)
 if a==1:g[cursor]=1-g[cursor];history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:cycle=(cycle+1)%4;cursor=(cursor+3)%8;history=(history+(3,))[-8:]
 elif a==4:correct=sum(int(g[i]==MESSAGE[i]) for i in range(8));errors=8-correct;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(g),cursor,cycle,correct,errors,history)
 return tuple(g),cursor,cycle,correct,errors,history,snapshot
for q in LEVELS:
 s=((0,1,1,0,1,0,0,1),0,0,8,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHANNEL
  for row in range(3):
   for i,v in enumerate(g.guesses):
    x=8+i*6;y=12+row*13;col=ERASURE if i==(g.cursor+row*3)%8 else PACKET_A if v==0 else PACKET_B;f[y:y+9,x:x+5]=col
  x=8+g.cursor*6;f[50:56,x:x+5]=RECONSTRUCT;f[54:58,8:8+g.correct*6]=CORRECT;f[7:10,8:8+g.errors*6]=ERROR;f[54:58,53:58]=CYCLE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A185(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a185",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.guesses,self.cursor,self.cycle,self.correct,self.errors,self.history,self.snapshot=((0,1,1,0,1,0,0,1),0,0,8,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.guesses,self.cursor,self.cycle,self.correct,self.errors,self.history,self.snapshot=advance((self.guesses,self.cursor,self.cycle,self.correct,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.guesses,self.cursor,self.cycle,self.correct,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
