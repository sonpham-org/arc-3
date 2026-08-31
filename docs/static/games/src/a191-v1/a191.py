"""a191 Interleaved Message -- demultiplex alternating senders from a pilot phase."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LANE,PULSE_A,PULSE_B,PILOT,ASSIGNED,CURSOR,CORRECT,ERROR=13,1,12,14,10,8,6,4,9
BAD=15
STREAM=(1,0,1,1,0,0,1,0,1,0,0,1)
LEVELS=[
 {"name":"Assign Pulse","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Read Pilot","seq":(3,1)},{"name":"Separate Senders","seq":(1,2,3,4,2)},
 {"name":"Unknown Phase","seq":(1,3,2,1,4,3,2)},{"name":"Interleaved Message","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 owners,cursor,phase,correct,errors,history,snapshot=s
 if a==1:owners^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%12;history=(history+(2,))[-8:]
 elif a==3:phase=1-phase;history=(history+(3,))[-8:]
 elif a==4:correct=sum(int(((owners>>i)&1)==((i+phase)&1)) for i in range(12));errors=12-correct;history=(history+(4,))[-8:]
 elif a==5:snapshot=(owners,cursor,phase,correct,errors,history)
 return owners,cursor,phase,correct,errors,history,snapshot
for q in LEVELS:
 s=(0b101010101010,0,0,12,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=LANE
  for i,bit in enumerate(STREAM):
   x=7+i*4;col=PULSE_A if bit else PULSE_B;f[14:23,x:x+3]=col
   owner=(g.owners>>i)&1;y=31 if owner else 43;f[y:y+8,x:x+3]=ASSIGNED if owner==((i+g.phase)&1) else col
  f[8:12,7+g.phase*4:10+g.phase*4]=PILOT;f[24:28,7+g.cursor*4:10+g.cursor*4]=CURSOR
  f[54:58,7:7+min(12,g.correct)*3]=CORRECT;f[54:58,47:47+min(4,g.errors)*3]=ERROR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A191(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a191",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.owners,self.cursor,self.phase,self.correct,self.errors,self.history,self.snapshot=(0b101010101010,0,0,12,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.owners,self.cursor,self.phase,self.correct,self.errors,self.history,self.snapshot=advance((self.owners,self.cursor,self.phase,self.correct,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.owners,self.cursor,self.phase,self.correct,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
