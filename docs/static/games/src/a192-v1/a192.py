"""a192 Self-Clocking Path -- re-encode a route so data transitions recover timing."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SCOPE,ZERO,ONE,TRANSITION,CURSOR,CLOCKED,LOST,PHASE=14,1,8,12,10,13,4,6,11
BAD=15
LEVELS=[
 {"name":"Flip Signal","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Shift Receiver","seq":(3,1)},{"name":"Count Transitions","seq":(1,2,3,4,2)},
 {"name":"Break Long Run","seq":(1,3,2,1,4,3,2)},{"name":"Self-Clocking Path","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 bits,cursor,phase,clocked,lost,history,snapshot=s;b=list(bits)
 if a==1:b[cursor]=1-b[cursor];history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%12;history=(history+(2,))[-8:]
 elif a==3:phase=(phase+1)%4;cursor=(cursor+2)%12;history=(history+(3,))[-8:]
 elif a==4:clocked=sum(int(b[i]!=b[(i-1)%12]) for i in range(12));lost=12-clocked;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(b),cursor,phase,clocked,lost,history)
 return tuple(b),cursor,phase,clocked,lost,history,snapshot
INITIAL=(0,1,0,1,1,0,1,0,0,1,0,1)
for q in LEVELS:
 s=(INITIAL,0,0,9,3,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SCOPE
  for i,bit in enumerate(g.bits):
   x=7+i*4;y=18 if bit else 31;f[y:y+10,x:x+3]=ONE if bit else ZERO
   if bit!=g.bits[(i-1)%12]:f[42:50,x:x+2]=TRANSITION
  f[12:15,7+g.cursor*4:10+g.cursor*4]=CURSOR;f[54:58,7:7+min(12,g.clocked)*3]=CLOCKED;f[54:58,47:47+min(4,g.lost)*3]=LOST;f[8:11,50:58]=PHASE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A192(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a192",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bits,self.cursor,self.phase,self.clocked,self.lost,self.history,self.snapshot=(INITIAL,0,0,9,3,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bits,self.cursor,self.phase,self.clocked,self.lost,self.history,self.snapshot=advance((self.bits,self.cursor,self.phase,self.clocked,self.lost,self.history,self.snapshot),a)
  elif a==6:
   if (self.bits,self.cursor,self.phase,self.clocked,self.lost,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
