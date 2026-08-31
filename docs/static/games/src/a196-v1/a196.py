"""a196 Module Polarity -- orient a functional loop while alternating interfaces."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,PLATE,POSITIVE,NEGATIVE,MODULE,CURSOR,VALID,INVALID,FUNCTION=5,1,12,14,8,13,4,6,10
BAD=15
LEVELS=[
 {"name":"Flip Module","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Change Function","seq":(3,1)},{"name":"Check Polarity","seq":(1,2,3,4,2)},
 {"name":"Close Loop","seq":(1,3,2,1,4,3,2)},{"name":"Module Polarity","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 orientation,cursor,function,valid,invalid,history,snapshot=s
 if a==1:orientation^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:function=(function+1)%4;history=(history+(3,))[-8:]
 elif a==4:valid=sum(int(((orientation>>i)&1)!=((orientation>>((i+1)%8))&1)) for i in range(8));invalid=8-valid+int(orientation.bit_count()%4!=function);history=(history+(4,))[-8:]
 elif a==5:snapshot=(orientation,cursor,function,valid,invalid,history)
 return orientation,cursor,function,valid,invalid,history,snapshot
for q in LEVELS:
 s=(0b01010101,0,0,8,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=PLATE
  pos=((26,8),(39,12),(47,24),(39,39),(26,45),(13,39),(7,24),(13,12))
  for i,(x,y) in enumerate(pos):
   bit=(g.orientation>>i)&1;f[y:y+10,x:x+10]=MODULE;f[y+2:y+8,x+2:x+5]=POSITIVE if bit else NEGATIVE;f[y+2:y+8,x+5:x+8]=NEGATIVE if bit else POSITIVE
   if i==g.cursor:f[y-2:y,x:x+10]=CURSOR
  f[26:38,27:39]=FUNCTION;f[54:58,8:8+g.valid*5]=VALID;f[54:58,49:49+min(3,g.invalid)*3]=INVALID
  if g.bad:f[1:4,18:46]=BAD
  return f
class A196(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a196",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.orientation,self.cursor,self.function,self.valid,self.invalid,self.history,self.snapshot=(0b01010101,0,0,8,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.orientation,self.cursor,self.function,self.valid,self.invalid,self.history,self.snapshot=advance((self.orientation,self.cursor,self.function,self.valid,self.invalid,self.history,self.snapshot),a)
  elif a==6:
   if (self.orientation,self.cursor,self.function,self.valid,self.invalid,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
