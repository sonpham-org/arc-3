"""a181 Certificate Path -- lay sparse checkpoints that independently verify a route."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,MAZE,PASSAGE,DOOR,CHECKPOINT,ARROW,CURSOR,VERIFIED,GAP,EXCESS=2,8,7,12,14,10,13,4,6,11
BAD=15
ONE_WAY=(2,5,8,10)
LEVELS=[
 {"name":"Place Checkpoint","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Turn Arrow","seq":(3,1)},{"name":"Verify Segment","seq":(1,2,3,4,2)},
 {"name":"Cover One-way Doors","seq":(1,3,2,1,4,3,2)},{"name":"Certificate Path","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 checkpoints,cursor,direction,verified,gaps,excess,history,snapshot=s
 if a==1:checkpoints^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%12;history=(history+(2,))[-8:]
 elif a==3:direction=(direction+1)%4;history=(history+(3,))[-8:]
 elif a==4:verified=sum(int((checkpoints>>i)&1) for i in ONE_WAY);gaps=len(ONE_WAY)-verified;excess=max(0,checkpoints.bit_count()-len(ONE_WAY));history=(history+(4,))[-8:]
 elif a==5:snapshot=(checkpoints,cursor,direction,verified,gaps,excess,history)
 return checkpoints,cursor,direction,verified,gaps,excess,history,snapshot
for q in LEVELS:
 s=(0b000000100100,0,0,2,2,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MAZE
  for i in range(12):
   x=8+(i%4)*13;y=11+(i//4)*15;f[y:y+11,x:x+11]=DOOR if i in ONE_WAY else PASSAGE
   if (g.checkpoints>>i)&1:f[y+2:y+9,x+2:x+9]=CHECKPOINT
   if i==g.cursor:f[y-3:y,x:x+11]=CURSOR
  f[54:58,8:8+g.verified*10]=VERIFIED;f[7:10,8:8+g.gaps*10]=GAP;f[54:58,50:50+g.excess*2]=EXCESS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A181(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a181",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.checkpoints,self.cursor,self.direction,self.verified,self.gaps,self.excess,self.history,self.snapshot=(0b000000100100,0,0,2,2,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.checkpoints,self.cursor,self.direction,self.verified,self.gaps,self.excess,self.history,self.snapshot=advance((self.checkpoints,self.cursor,self.direction,self.verified,self.gaps,self.excess,self.history,self.snapshot),a)
  elif a==6:
   if (self.checkpoints,self.cursor,self.direction,self.verified,self.gaps,self.excess,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
